#!/usr/bin/env python3
"""Step 16B-2: preliminary graph-following bicycle corridor investigations.

Offline only. See BIKE_RECOMMENDATIONS_METHODOLOGY.md for exact assumptions.
Uses OSMnx 2.1.1 GraphML loading and one NetworkX multi-source Dijkstra search:
https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.shortest_paths.weighted.multi_source_dijkstra.html
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile
from time import perf_counter

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
from pyproj import CRS, Transformer
import shapely
from shapely.geometry import LineString, MultiLineString, Point, mapping, shape

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    'graph': ROOT / 'data/processed/networks/baku_bike.graphml',
    'study': ROOT / 'data/processed/networks/baku_bike_study_area.geojson',
    'ayna': ROOT / 'data/processed/transport/cycleways.geojson',
    'grid': ROOT / 'data/processed/grid/baku_grid_scored.geojson',
    'pois': ROOT / 'data/processed/pois/essential_services.geojson',
}
OUTPUT = ROOT / 'data/processed/recommendations/bike_recommendations.geojson'
METHOD = 'baku-bike-corridors-v1.0'
METRIC_CRS = 'EPSG:32639'
TO_GEO = Transformer.from_crs(METRIC_CRS, 4326, always_xy=True).transform
TO_METRIC = Transformer.from_crs(4326, METRIC_CRS, always_xy=True).transform
MIN_PRIORITY, MIN_NEW_M, MAX_ROUTE_M, MAX_RESULTS = 60, 200, 4000, 15
ANCHOR_SNAP_M, TARGET_SNAP_M, POI_SNAP_M = 25, 150, 100
AYNA_EXCLUSION_M, OSM_EXCLUSION_M = 25, 10
COVERAGE_M, DESTINATION_RADIUS_M = 500, 500
OVERLAP_BUFFER_M, OVERLAP_FRACTION = 20, 0.60
ALLOWED_BICYCLE = {'yes', 'designated', 'permissive', 'official'}
RESTRICTED = {'no', 'private', 'customers', 'destination', 'delivery', 'permit', 'agricultural', 'forestry', 'military'}
BASE_COST = {'cycleway': 1., 'living_street': 1.2, 'residential': 1.5, 'path': 1.6,
             'pedestrian': 1.8, 'track': 2., 'unclassified': 2.5, 'service': 2.8,
             'tertiary': 3., 'tertiary_link': 3.3, 'secondary': 4., 'secondary_link': 4.3,
             'primary': 5., 'primary_link': 5.3, 'busway': 5.}
USEFUL_CATEGORIES = {'HOSPITAL': 0, 'SCHOOL': 1, 'KINDERGARTEN': 2, 'PHARMACY': 3}
LIMITATIONS = [
    'Preliminary investigation corridors; not construction-ready, safe, approved or verified legal access.',
    'Straight-line coverage from grid interior representative points, not walking/cycling-network access.',
    'Modeled population and incomplete AYNA/OSM infrastructure mapping; null population is excluded, never imputed.',
    'AYNA-to-node snaps are proximity associations requiring field checks; no geometric gap connectors are added.',
    'Directions follow existing directed edges with extra tag exclusions; no missing contraflow or component links are invented.',
    'Turn restrictions, schedules, traffic stress, crossings, topography and engineering feasibility remain unverified.',
    'Each benefit is standalone; overlapping benefits must not be summed as a combined citywide gain.',
]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def report(label, value):
    print(label + ': ' + json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def raw_tags(data):
    tags = data.get('osm_tags_json')
    tags = json.loads(tags) if isinstance(tags, str) else tags
    if not isinstance(tags, dict):
        raise ValueError('Mandatory original OSM way tags unavailable.')
    return {key: str(value).strip().lower() for key, value in tags.items() if value is not None}


def classify_existing(tags):
    return (tags.get('highway') == 'cycleway'
            or (tags.get('highway') in {'path', 'track'} and tags.get('bicycle') == 'designated')
            or any(tags.get(k) in {'lane', 'track', 'opposite', 'opposite_lane', 'opposite_track', 'shared_lane', 'separate'}
                   for k in ('cycleway', 'cycleway:left', 'cycleway:right', 'cycleway:both')))


def speed_kph(value):
    if value is None:
        return None
    numbers = []
    for token in value.split(';'):
        match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(mph|km/h|kph)?\s*', token)
        if not match:
            return None
        numbers.append(float(match[1]) * (1.609344 if match[2] == 'mph' else 1))
    return max(numbers)


def edge_policy(data):
    tags = raw_tags(data)
    highway, bicycle = tags.get('highway'), tags.get('bicycle')
    rejection = None
    if highway not in BASE_COST:
        rejection = 'excluded_highway_type'
    elif bicycle is not None and bicycle not in ALLOWED_BICYCLE:
        rejection = 'restricted_bicycle_access'
    elif tags.get('access') in RESTRICTED:
        rejection = 'restricted_access'
    elif any(':conditional' in key and key.startswith(('access', 'bicycle', 'oneway')) for key in tags):
        rejection = 'unsupported_conditional_access'
    elif highway in {'busway', 'path', 'track', 'pedestrian'} and bicycle not in ALLOWED_BICYCLE:
        rejection = 'explicit_bicycle_permission_required'
    elif tags.get('service') in {'parking_aisle', 'driveway', 'emergency_access', 'private'}:
        rejection = 'restricted_service_purpose'
    backward = bool(data.get('reversed', False)) ^ (tags.get('oneway') in {'-1', 'reverse'})
    direction = 'backward' if backward else 'forward'
    directional_access = tags.get('bicycle:' + direction)
    if directional_access is not None and directional_access not in ALLOWED_BICYCLE:
        rejection = 'directional_bicycle_prohibition'
    if any(tags.get(k) not in {None, 'yes', '1', 'true', 'no', '0', 'false', '-1', 'reverse'}
           for k in ('oneway', 'oneway:bicycle')):
        rejection = 'unsupported_oneway_rule'
    if ((tags.get('oneway:bicycle') in {'yes', '1', 'true'} and backward)
            or (tags.get('oneway:bicycle') in {'-1', 'reverse'} and not backward)):
        rejection = 'bicycle_oneway_direction'
    speed = speed_kph(tags.get('maxspeed'))
    if speed is not None and speed > 60:
        rejection = 'speed_over_60kph'
    flags = []
    factor = BASE_COST.get(highway, 1.)
    existing = classify_existing(tags)
    if existing:
        factor = min(factor, 1.2)
        flags.append('existing_osm_infrastructure_traversed')
    surface = tags.get('surface')
    if surface is None:
        factor += .5; flags.append('unknown_surface')
    elif surface in {'gravel', 'fine_gravel', 'ground', 'dirt', 'earth', 'unpaved', 'sett', 'cobblestone', 'sand', 'mud'}:
        factor += 1.; flags.append('rough_or_unpaved_surface')
    elif surface not in {'asphalt', 'paved', 'concrete', 'paving_stones', 'concrete:plates'}:
        factor += .75; flags.append('unassessed_surface')
    if highway not in {'cycleway', 'path', 'track', 'pedestrian'}:
        if speed is None:
            factor += .75; flags.append('unknown_speed')
        elif speed > 50:
            factor += 2.5; flags.append('speed_over_50kph')
        elif speed > 30:
            factor += 1.; flags.append('speed_over_30kph')
    if tags.get('lit') != 'yes':
        factor += .25; flags.append('lighting_unconfirmed')
    if bicycle is None and highway != 'cycleway':
        factor += .25; flags.append('implicit_bicycle_permission')
    if highway == 'service':
        factor += .5 if tags.get('service') == 'alley' else 1.
        flags.append('uncertain_service_road')
    if highway == 'busway':
        flags.append('busway_requires_operational_assessment')
    for tag in ('bridge', 'tunnel'):
        if tags.get(tag) not in (None, 'no', 'false', '0'):
            factor += .75; flags.append(tag + '_requires_assessment')
    if tags.get('oneway:bicycle') == 'no' and data.get('oneway'):
        flags.append('missing_bicycle_contraflow_not_added')
    return {'rejection': rejection, 'factor': factor, 'flags': sorted(flags), 'existing': existing}


def node_allowed(data):
    if str(data.get('access', '')).lower() in RESTRICTED or str(data.get('bicycle', '')).lower() in RESTRICTED:
        return False
    barrier = data.get('barrier')
    return (barrier in (None, 'no', 'bollard', 'entrance', 'kerb')
            or str(data.get('bicycle', '')).lower() in ALLOWED_BICYCLE)


def build_routing_graph(graph):
    routing, counts = nx.DiGraph(), Counter()
    allowed_nodes = {n for n, p in graph.nodes(data=True) if node_allowed(p)}
    for u, v, key, data in sorted(graph.edges(keys=True, data=True), key=lambda e: e[:3]):
        policy = edge_policy(data)
        rejection = 'node_access_rejections' if u not in allowed_nodes or v not in allowed_nodes else policy['rejection']
        if rejection:
            counts[rejection] += 1
            continue
        length = float(data['geometry'].length)
        if not math.isfinite(length) or length <= 0:
            raise ValueError('Nonpositive/nonfinite source edge geometry length.')
        factor = policy['factor']
        flags = list(policy['flags'])
        if graph.nodes[u].get('barrier') or graph.nodes[v].get('barrier'):
            factor += .5; flags.append('barrier_requires_assessment')
        cost = length * factor
        previous = routing.get_edge_data(u, v)
        if previous is None or (cost, key) < (previous['cost'], previous['edge_key']):
            routing.add_edge(u, v, edge_key=key, cost=cost, factor=factor, flags=sorted(flags))
    counts['retained_directed_edges'] = routing.number_of_edges()
    counts['retained_nodes'] = routing.number_of_nodes()
    return routing, dict(counts)


def route_search(routing, sources):
    sources = sorted(n for n in sources if n in routing and routing.out_degree(n) > 0)
    if not sources:
        return {}, {}
    max_factor = max(p['factor'] for _, _, p in routing.edges(data=True))
    # One directed search, bounded above by the cost of any <=4000m route.
    return nx.multi_source_dijkstra(routing, sources, cutoff=MAX_ROUTE_M * max_factor, weight='cost')


def trace_path(graph, routing, nodes):
    if len(nodes) < 2 or len(set(nodes)) != len(nodes):
        raise ValueError('A routed path must contain distinct, connected nodes.')
    coordinates, edges = [], []
    for u, v in zip(nodes, nodes[1:]):
        if not routing.has_edge(u, v):
            raise ValueError('Route jumps a disconnected component or invalid travel direction.')
        key = routing[u][v]['edge_key']
        geometry = graph.edges[u, v, key]['geometry']
        coords = list(geometry.coords)
        if (Point(coords[0]).distance(Point(graph.nodes[u]['x'], graph.nodes[u]['y'])) > 1e-6
                or Point(coords[-1]).distance(Point(graph.nodes[v]['x'], graph.nodes[v]['y'])) > 1e-6
                or (coordinates and Point(coordinates[-1]).distance(Point(coords[0])) > 1e-6)):
            raise ValueError('Source edge geometry does not follow continuous directed graph endpoints.')
        coordinates.extend(coords if not coordinates else coords[1:])
        edges.append((u, v, key))
    return LineString(coordinates), edges


def line_parts(geometry):
    if geometry.geom_type == 'LineString':
        return [geometry] if geometry.length > 1e-8 else []
    if geometry.geom_type in ('MultiLineString', 'GeometryCollection'):
        return [line for part in geometry.geoms for line in line_parts(part)]
    return []


def proposed_geometry(trace, existing_mask):
    parts = line_parts(trace.difference(existing_mask))
    return parts[0] if len(parts) == 1 else MultiLineString(parts) if parts else None


def valid_lengths(new_length, total_length):
    return new_length >= MIN_NEW_M and new_length <= total_length + 1e-6 and total_length <= MAX_ROUTE_M


def substantially_overlaps(a, b):
    return max(a.intersection(b.buffer(OVERLAP_BUFFER_M)).length / a.length,
               b.intersection(a.buffer(OVERLAP_BUFFER_M)).length / b.length) >= OVERLAP_FRACTION


def coverage(geometry, ctx):
    indices = ctx['origin_tree'].query(geometry, predicate='dwithin', distance=COVERAGE_M)
    known, unknown, excluded, partial = [], 0, 0, 0
    for i in indices:
        cell = ctx['props'][i]
        if cell['nearest_cycleway_m'] <= COVERAGE_M:
            continue
        if ctx['existing_osm_distances'][i] <= COVERAGE_M:
            excluded += 1
            continue
        if cell['population'] is None:
            unknown += 1
        else:
            known.append(int(i))
            partial += cell.get('valid_pixel_fraction') is not None and cell['valid_pixel_fraction'] < 1
    known.sort()
    population = math.fsum(ctx['props'][i]['population'] for i in known)
    before = math.fsum(ctx['props'][i]['population'] * ctx['props'][i]['nearest_cycleway_m'] for i in known)
    after = math.fsum(ctx['props'][i]['population'] * min(ctx['props'][i]['nearest_cycleway_m'],
                                                       ctx['origins'][i].distance(geometry)) for i in known)
    return {'population_coverage_gain': population, 'newly_covered_cells': len(known),
            'unknown_population_cells': unknown, 'existing_osm_coverage_excluded_cells': excluded,
            'partial_population_cells': partial, 'current_access_m': before / population if population > 0 else None,
            'new_access_m': after / population if population > 0 else None,
            'access_improvement_m': (before - after) / population if population > 0 else None}


def load_geo(path, kinds, required):
    document = json.loads(path.read_bytes())
    if document.get('type') != 'FeatureCollection' or not document.get('features'):
        raise ValueError(f'{path.name}: mandatory nonempty FeatureCollection required.')
    props = [f['properties'] for f in document['features']]
    if any(any(k not in p for k in required) for p in props):
        raise ValueError(f'{path.name}: missing required source fields.')
    ids = [p['id'] for p in props]
    if any(type(i) is not str or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError(f'{path.name}: unique nonempty string IDs required.')
    frame = gpd.read_file(path)
    coords = shapely.get_coordinates(frame.geometry.array)
    if (frame.crs is None or frame.crs.to_epsg() != 4326 or len(frame) != len(props)
            or frame['id'].tolist() != ids or frame.geometry.isna().any() or frame.is_empty.any()
            or not frame.is_valid.all() or not frame.geom_type.isin(kinds).all()
            or not np.isfinite(coords).all() or shapely.has_z(frame.geometry.array).any()
            or (np.abs(coords[:, 0]) > 180).any() or (np.abs(coords[:, 1]) > 90).any()):
        raise ValueError(f'{path.name}: invalid geometry/schema/2D EPSG:4326 coordinates.')
    report('INPUT SCHEMA', {'file': str(path.relative_to(ROOT)), 'count': len(props),
                            'geometry_types': frame.geom_type.value_counts().to_dict(),
                            'fields': sorted(frame.columns)})
    return props, frame.to_crs(METRIC_CRS).geometry.to_numpy(), document


def nearest_node(point, ctx):
    indices = ctx['node_tree'].query_nearest(point, all_matches=True)
    index = min(indices, key=lambda i: ctx['node_ids'][i])
    return ctx['node_ids'][index], float(point.distance(ctx['node_points'][index]))


def prepare_context(graph, area, lane_props, lanes, props, origins, poi_props, pois, audits):
    routing, access_stats = build_routing_graph(graph)
    node_ids = sorted(routing.nodes)
    node_points = np.array([Point(graph.nodes[n]['x'], graph.nodes[n]['y']) for n in node_ids], dtype=object)
    existing_osm = [p['geometry'] for _, _, p in graph.edges(data=True) if classify_existing(raw_tags(p))]
    osm_union = shapely.union_all(existing_osm)
    ayna_union = shapely.union_all(lanes)
    existing_mask = ayna_union.buffer(AYNA_EXCLUSION_M).union(osm_union.buffer(OSM_EXCLUSION_M))
    if existing_osm:
        tree = shapely.STRtree(existing_osm)
        existing_distances = shapely.distance(origins, np.array(existing_osm, dtype=object)[tree.nearest(origins)])
    else:
        existing_distances = np.full(len(origins), np.inf)
    ctx = {'graph': graph, 'area': area, 'lane_props': lane_props, 'lanes': lanes,
           'props': props, 'origins': origins, 'poi_props': poi_props, 'pois': pois,
           'routing': routing, 'access_stats': access_stats, 'node_ids': node_ids, 'node_points': node_points,
           'node_tree': shapely.STRtree(node_points), 'origin_tree': shapely.STRtree(origins),
           'poi_tree': shapely.STRtree(pois), 'existing_mask': existing_mask, 'osm_union': osm_union,
           'existing_osm_distances': existing_distances, 'audits': audits, 'anchors': {}}
    if node_ids:
        pairs = ctx['node_tree'].query(lanes, predicate='dwithin', distance=ANCHOR_SNAP_M)
        lane_tree = shapely.STRtree(lanes)
        for index in sorted(set(pairs[1]), key=lambda i: node_ids[i]):
            node, point = node_ids[index], node_points[index]
            if routing.out_degree(node) == 0:
                continue
            candidates = lane_tree.query_nearest(point, all_matches=True)
            lane = min(candidates, key=lambda i: lane_props[i]['id'])
            ctx['anchors'][node] = {'lane_index': int(lane), 'snap_m': float(point.distance(lanes[lane]))}
    return ctx


def load_inputs():
    audits = {name: {'file': str(path.relative_to(ROOT)), 'sha256': digest(path)} for name, path in INPUTS.items()}
    _, areas, study = load_geo(INPUTS['study'], ['Polygon', 'MultiPolygon'], ['id'])
    lp, lanes, _ = load_geo(INPUTS['ayna'], ['LineString', 'MultiLineString'], ['id', 'name', 'source'])
    props, polygons, _ = load_geo(INPUTS['grid'], ['Polygon', 'MultiPolygon'],
                                  ['id', 'population', 'bike_priority', 'nearest_cycleway_m', 'scoring_model_version'])
    pp, pois, _ = load_geo(INPUTS['pois'], ['Point'], ['id', 'name', 'category'])
    if len(areas) != 1 or len(lanes) != 60 or any(p['source'] != 'AYNA' for p in lp):
        raise ValueError('Expected the saved study area and all 60 AYNA line features.')
    if study['metadata']['graphml_sha256'] != audits['graph']['sha256']:
        raise ValueError('Graph differs from validated study-area artifact; refusing stale/mismatched inputs.')
    for p in props:
        for field in ('population', 'bike_priority', 'nearest_cycleway_m'):
            v = p[field]
            if v is None and field != 'nearest_cycleway_m':
                continue
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0 or (field == 'bike_priority' and v > 100):
                raise ValueError(f"Invalid {field} for {p['id']}.")
    origins = shapely.point_on_surface(polygons)
    lane_tree = shapely.STRtree(lanes)
    baseline = shapely.distance(origins, lanes[lane_tree.nearest(origins)])
    if not np.allclose(baseline, [p['nearest_cycleway_m'] for p in props], rtol=0, atol=1e-6):
        raise ValueError('Stored cycling baseline differs from current AYNA linework.')
    graph = ox.load_graphml(INPUTS['graph'], edge_dtypes={'length_utm_m': float})
    if not isinstance(graph, nx.MultiDiGraph) or CRS(graph.graph['crs']).to_epsg() != 32639:
        raise ValueError('Expected existing directed EPSG:32639 MultiDiGraph.')
    if graph.number_of_nodes() != study['metadata']['validation_summary']['nodes'] or graph.number_of_edges() != study['metadata']['validation_summary']['edges']:
        raise ValueError('Graph node/edge counts differ from validated network metadata.')
    report('EXISTING GRAPH', {'nodes': graph.number_of_nodes(), 'directed_edges': graph.number_of_edges(),
                              'crs': str(graph.graph['crs']), 'osmnx_version': ox.__version__, 'networkx_version': nx.__version__,
                              'edge_fields': sorted({k for _, _, p in graph.edges(data=True) for k in p}),
                              'directions': 'existing directed edges only; additional tag exclusions; no contraflow edges added'})
    return prepare_context(graph, areas[0], lp, lanes, props, origins, pp, pois, audits)


def choose_endpoint(origin, ctx):
    nearby = ctx['poi_tree'].query(origin, predicate='dwithin', distance=DESTINATION_RADIUS_M)
    useful = [i for i in nearby if ctx['poi_props'][i]['category'] in USEFUL_CATEGORIES
              and ctx['area'].covers(ctx['pois'][i])]
    useful.sort(key=lambda i: (USEFUL_CATEGORIES[ctx['poi_props'][i]['category']], origin.distance(ctx['pois'][i]), ctx['poi_props'][i]['id']))
    for i in useful:
        node, snap = nearest_node(ctx['pois'][i], ctx)
        if snap <= POI_SNAP_M and origin.distance(Point(ctx['graph'].nodes[node]['x'], ctx['graph'].nodes[node]['y'])) <= COVERAGE_M:
            return node, snap, int(i)
    node, snap = nearest_node(origin, ctx)
    return node, snap, None


def stable_id(properties, geometry):
    payload = [METHOD, properties['source_grid_id'], properties['source_cycleway_id'],
               properties['destination_id'], properties['route_edges'],
               shapely.to_wkt(shapely.normalize(geometry), rounding_precision=6)]
    return 'baku:bike-corridor:' + hashlib.sha256(canonical(payload).encode()).hexdigest()


def ranking_key(feature):
    p = feature['properties']
    return (-p['ranking_score'], -p['population_coverage_gain'], -p['priority'],
            -p['routing_suitability'], p['source_grid_id'], p['id'])


def build_document(ctx):
    targets = [i for i, p in enumerate(ctx['props']) if p['population'] is not None and p['bike_priority'] is not None
               and p['bike_priority'] >= MIN_PRIORITY and ctx['area'].contains(ctx['origins'][i])]
    targets.sort(key=lambda i: ctx['props'][i]['id'])
    stats = dict.fromkeys(('routing_failures', 'access_rejections', 'length_rejections', 'zero_gain_rejections',
                          'duplicate_corridors', 'qualified_beyond_limit', 'final_count'), 0)
    stats.update(eligible_targets=len(targets), ayna_connection_nodes=len(ctx['anchors']))
    costs, paths = route_search(ctx['routing'], ctx['anchors'])
    candidates = []
    for i in targets:
        if not ctx['node_ids']:
            stats['access_rejections'] += 1; continue
        node, snap, poi = choose_endpoint(ctx['origins'][i], ctx)
        if snap > (TARGET_SNAP_M if poi is None else POI_SNAP_M):
            stats['access_rejections'] += 1; continue
        if node not in paths:
            stats['routing_failures'] += 1; continue
        if len(paths[node]) < 2:
            stats['length_rejections'] += 1; continue
        trace, edges = trace_path(ctx['graph'], ctx['routing'], paths[node])
        proposed = proposed_geometry(trace, ctx['existing_mask'])
        if proposed is None:
            stats['length_rejections'] += 1; continue
        # Measure the exact exported geometry after CRS roundtrip.
        geographic = shapely.transform(proposed, TO_GEO, interleaved=False)
        proposed = shapely.transform(geographic, TO_METRIC, interleaved=False)
        if not valid_lengths(proposed.length, trace.length):
            stats['length_rejections'] += 1; continue
        benefit = coverage(proposed, ctx)
        if benefit['population_coverage_gain'] <= 0:
            stats['zero_gain_rejections'] += 1; continue
        seed, start = ctx['props'][i], paths[node][0]
        anchor = ctx['anchors'][start]
        lane = ctx['lane_props'][anchor['lane_index']]
        destination = ctx['poi_props'][poi] if poi is not None else None
        suitability = trace.length / costs[node]
        flags = sorted({'ayna_snap_requires_field_check', 'directionality_and_safety_require_assessment',
                        *(flag for u, v, _ in edges for flag in ctx['routing'][u][v]['flags'])})
        if destination:
            flags = sorted([*flags, 'destination_status_and_public_access_unverified'])
        p = {'priority': seed['bike_priority'], 'length_m': float(proposed.length), **benefit,
             'start_name': lane['name'], 'end_name': destination['name'] if destination else None,
             'reason': ['high_bike_priority_target', 'directed_path_from_AYNA_proximity_anchor',
                        'at_least_200m_proposed_new_infrastructure', 'positive_modeled_population_gain',
                        'preliminary_requires_field_and_engineering_assessment'],
             'source_grid_id': seed['id'], 'network_distance_m': trace.length,
             'new_corridor_length_m': float(proposed.length), 'existing_connection_length_m': max(0., trace.length - proposed.length),
             'routing_risk_flags': flags, 'scoring_model_version': seed['scoring_model_version'], 'method_version': METHOD,
             'source_cycleway_id': lane['id'], 'anchor_node': start, 'target_node': node,
             'anchor_snap_m': anchor['snap_m'], 'target_snap_m': snap,
             'source_grid_endpoint_distance_m': ctx['origins'][i].distance(Point(ctx['graph'].nodes[node]['x'], ctx['graph'].nodes[node]['y'])),
             'destination_id': destination['id'] if destination else None,
             'destination_category': destination['category'] if destination else None,
             'route_edges': [list(e) for e in edges], 'routing_cost': costs[node], 'routing_suitability': suitability,
             'ranking_score': benefit['population_coverage_gain'] * (.5 + .5 * seed['bike_priority'] / 100) * suitability}
        p['id'] = stable_id(p, proposed)
        candidates.append({'type': 'Feature', 'id': p['id'], 'properties': p, 'geometry': mapping(geographic)})
    retained, geometries = [], []
    for feature in sorted(candidates, key=ranking_key):
        geometry = shapely.transform(shape(feature['geometry']), TO_METRIC, interleaved=False)
        if any(substantially_overlaps(geometry, previous) for previous in geometries):
            stats['duplicate_corridors'] += 1; continue
        retained.append(feature); geometries.append(geometry)
    stats['qualified_beyond_limit'] = max(0, len(retained) - MAX_RESULTS)
    selected = retained[:MAX_RESULTS]
    stats['final_count'] = len(selected)
    return {'type': 'FeatureCollection', 'features': selected, 'screening': stats,
            'metadata': {'method_version': METHOD, 'metric_crs': METRIC_CRS, 'output_crs': 'EPSG:4326',
                         'inputs': ctx['audits'], 'edge_access_screening': ctx['access_stats'], 'limitations': LIMITATIONS,
                         'coverage_definition': 'baseline AYNA >500m, distance to complete proposed NEW geometry <=500m, known OSM infrastructure >500m',
                         'ranking_formula': 'population_coverage_gain * (0.5 + 0.5 * seed_bike_priority / 100) * (network_distance_m / routing_cost)',
                         'priority_definition': 'unchanged target-cell bike_priority; routing cost and safety are distinct',
                         'parameters': {'min_priority': MIN_PRIORITY, 'min_new_m': MIN_NEW_M, 'max_route_m': MAX_ROUTE_M,
                                        'anchor_snap_m': ANCHOR_SNAP_M, 'target_snap_m': TARGET_SNAP_M, 'poi_snap_m': POI_SNAP_M,
                                        'ayna_exclusion_m': AYNA_EXCLUSION_M, 'osm_exclusion_m': OSM_EXCLUSION_M,
                                        'coverage_m': COVERAGE_M, 'overlap_buffer_m': OVERLAP_BUFFER_M,
                                        'overlap_fraction': OVERLAP_FRACTION, 'max_results': MAX_RESULTS}}}


def is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def close(a, b, label):
    if not is_number(a) or not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-5):
        raise ValueError('Independent numeric mismatch: ' + label)


def verify_document(saved, expected, ctx):
    """Reconstruct directed chains and independently sum all-grid resident gains.

    Population verification uses scalar geometry distances, no coverage() helper,
    origin spatial index or cached OSM-distance array. Expected-document equality
    additionally checks deterministic selection, completeness and provenance.
    """
    if saved.get('type') != 'FeatureCollection' or type(saved.get('features')) is not list or len(saved['features']) > MAX_RESULTS:
        raise ValueError('Invalid recommendation FeatureCollection or result limit.')
    grid_lookup = {p['id']: (p, origin) for p, origin in zip(ctx['props'], ctx['origins'], strict=True)}
    lane_lookup = {p['id']: (p, line) for p, line in zip(ctx['lane_props'], ctx['lanes'], strict=True)}
    poi_lookup = {p['id']: (p, point) for p, point in zip(ctx['poi_props'], ctx['pois'], strict=True)}
    identifiers, previous_geometries = set(), []
    for feature in saved['features']:
        p = feature.get('properties', {})
        if (feature.get('type') != 'Feature' or type(p.get('id')) is not str or not p['id']
                or feature.get('id') != p['id'] or p['id'] in identifiers
                or not is_number(p.get('priority')) or not 0 <= p['priority'] <= 100
                or any(not is_number(p.get(k)) or p[k] <= 0 for k in (
                    'length_m', 'population_coverage_gain', 'network_distance_m', 'new_corridor_length_m',
                    'routing_cost', 'routing_suitability', 'ranking_score', 'access_improvement_m'))
                or type(p.get('reason')) is not list or not p['reason']
                or any(type(r) is not str or not r for r in p['reason'])
                or any(p.get(k) is not None and type(p[k]) is not str for k in ('start_name', 'end_name'))
                or any(k not in p for k in ('start_name', 'end_name'))
                or p.get('method_version') != METHOD):
            raise ValueError('Contract V1 field types, score bounds, identity or positive gain failed.')
        identifiers.add(p['id'])
        for field in ('newly_covered_cells', 'unknown_population_cells', 'existing_osm_coverage_excluded_cells', 'partial_population_cells'):
            if type(p.get(field)) is not int or p[field] < 0:
                raise ValueError('Invalid cell count: ' + field)
        if type(p.get('routing_risk_flags')) is not list or any(type(flag) is not str for flag in p['routing_risk_flags']):
            raise ValueError('Invalid routing risk flags.')
        if p.get('source_grid_id') not in grid_lookup or p.get('source_cycleway_id') not in lane_lookup:
            raise ValueError('Unknown grid or AYNA source identity.')
        seed, origin = grid_lookup[p['source_grid_id']]
        lane, lane_line = lane_lookup[p['source_cycleway_id']]
        if (seed['population'] is None or seed['bike_priority'] is None or seed['bike_priority'] < MIN_PRIORITY
                or not ctx['area'].contains(origin) or p['priority'] != seed['bike_priority']
                or p.get('scoring_model_version') != seed['scoring_model_version'] or p['start_name'] != lane['name']):
            raise ValueError('Source seed eligibility, priority, scoring version or lane name failed.')
        raw_edges = p.get('route_edges')
        if type(raw_edges) is not list or not raw_edges or any(type(e) is not list or len(e) != 3 or any(type(n) is not int for n in e) for e in raw_edges):
            raise ValueError('Invalid ordered source edge identifiers.')
        coordinates, route_nodes, total_cost, flags = [], [], [], {'ayna_snap_requires_field_check', 'directionality_and_safety_require_assessment'}
        for u, v, key in raw_edges:
            if not ctx['graph'].has_edge(u, v, key) or (route_nodes and route_nodes[-1] != u):
                raise ValueError('Route jumps a graph gap/component or uses an unavailable travel direction.')
            data = ctx['graph'].edges[u, v, key]
            policy = edge_policy(data)
            if policy['rejection'] or not node_allowed(ctx['graph'].nodes[u]) or not node_allowed(ctx['graph'].nodes[v]):
                raise ValueError('Route uses prohibited or unsupported bicycle access.')
            factor = policy['factor']
            flags.update(policy['flags'])
            if ctx['graph'].nodes[u].get('barrier') or ctx['graph'].nodes[v].get('barrier'):
                factor += .5; flags.add('barrier_requires_assessment')
            geometry = data['geometry']
            a, b = list(geometry.coords)[0], list(geometry.coords)[-1]
            if (Point(a).distance(Point(ctx['graph'].nodes[u]['x'], ctx['graph'].nodes[u]['y'])) > 1e-6
                    or Point(b).distance(Point(ctx['graph'].nodes[v]['x'], ctx['graph'].nodes[v]['y'])) > 1e-6
                    or (coordinates and Point(coordinates[-1]).distance(Point(a)) > 1e-6)):
                raise ValueError('Edge geometry is inconsistent with directed graph topology.')
            coordinates.extend(list(geometry.coords) if not coordinates else list(geometry.coords)[1:])
            route_nodes.extend([u, v] if not route_nodes else [v])
            total_cost.append(geometry.length * factor)
        if len(set(route_nodes)) != len(route_nodes) or route_nodes[0] != p.get('anchor_node') or route_nodes[-1] != p.get('target_node'):
            raise ValueError('Looping route or incorrect anchor/target nodes.')
        trace = LineString(coordinates)
        anchor_point, endpoint = Point(coordinates[0]), Point(coordinates[-1])
        snap = anchor_point.distance(lane_line)
        nearest_lane = min(zip(ctx['lane_props'], ctx['lanes']), key=lambda pair: (anchor_point.distance(pair[1]), pair[0]['id']))
        if snap > ANCHOR_SNAP_M or nearest_lane[0]['id'] != p['source_cycleway_id']:
            raise ValueError('Invalid AYNA proximity anchor; no gap connector may be invented.')
        close(p.get('anchor_snap_m'), snap, 'anchor snap')
        if p.get('destination_id') is not None:
            if p['destination_id'] not in poi_lookup:
                raise ValueError('Unknown named destination.')
            destination, target = poi_lookup[p['destination_id']]
            flags.add('destination_status_and_public_access_unverified')
            if (destination['category'] not in USEFUL_CATEGORIES or origin.distance(target) > DESTINATION_RADIUS_M
                    or not ctx['area'].covers(target) or p['end_name'] != destination['name']
                    or p.get('destination_category') != destination['category'] or endpoint.distance(target) > POI_SNAP_M
                    or origin.distance(endpoint) > COVERAGE_M):
                raise ValueError('Invalid source-backed useful destination or endpoint snap.')
        else:
            target = origin
            if p['end_name'] is not None or endpoint.distance(target) > TARGET_SNAP_M:
                raise ValueError('Invalid population-target endpoint snap or invented destination name.')
        close(p.get('target_snap_m'), endpoint.distance(target), 'target snap')
        close(p.get('source_grid_endpoint_distance_m'), origin.distance(endpoint), 'grid endpoint distance')
        if p['routing_risk_flags'] != sorted(flags):
            raise ValueError('Routing risk flags differ from actual traversed tags.')
        geographic = shape(feature['geometry'])
        xy = shapely.get_coordinates(geographic)
        if (geographic.geom_type not in {'LineString', 'MultiLineString'} or geographic.is_empty or not geographic.is_valid
                or shapely.has_z(geographic) or not np.isfinite(xy).all()
                or (np.abs(xy[:, 0]) > 180).any() or (np.abs(xy[:, 1]) > 90).any()):
            raise ValueError('Expected valid nonempty 2D EPSG:4326 line geometry.')
        proposed = shapely.transform(geographic, TO_METRIC, interleaved=False)
        reconstructed = proposed_geometry(trace, ctx['existing_mask'])
        if (reconstructed is None or shapely.hausdorff_distance(proposed, reconstructed) > 1e-6
                or not math.isclose(proposed.length, reconstructed.length, abs_tol=1e-5, rel_tol=1e-12)
                or not ctx['area'].buffer(1e-6).covers(proposed)
                or not valid_lengths(proposed.length, trace.length)):
            raise ValueError('New geometry/length differs from actual route minus existing bicycle infrastructure.')
        for field, value in [('length_m', proposed.length), ('new_corridor_length_m', proposed.length),
                             ('network_distance_m', trace.length), ('existing_connection_length_m', trace.length - proposed.length),
                             ('routing_cost', math.fsum(total_cost)), ('routing_suitability', trace.length / math.fsum(total_cost))]:
            close(p.get(field), value, field)
        if p['id'] != stable_id(p, proposed):
            raise ValueError('Unstable or incorrect recommendation ID.')
        if any(substantially_overlaps(proposed, previous) for previous in previous_geometries):
            raise ValueError('Selected corridors substantially overlap.')
        previous_geometries.append(proposed)
        residents, before, after = [], [], []
        counts = dict.fromkeys(('newly_covered_cells', 'unknown_population_cells', 'existing_osm_coverage_excluded_cells', 'partial_population_cells'), 0)
        xmin, ymin, xmax, ymax = proposed.bounds
        for cell_origin, cell in zip(ctx['origins'], ctx['props'], strict=True):
            # Bounding-box lower bound is independent of the production STRtree.
            if (cell['nearest_cycleway_m'] <= COVERAGE_M or cell_origin.x < xmin - COVERAGE_M
                    or cell_origin.x > xmax + COVERAGE_M or cell_origin.y < ymin - COVERAGE_M or cell_origin.y > ymax + COVERAGE_M):
                continue
            distance = cell_origin.distance(proposed)
            if distance > COVERAGE_M:
                continue
            if not ctx['osm_union'].is_empty and cell_origin.distance(ctx['osm_union']) <= COVERAGE_M:
                counts['existing_osm_coverage_excluded_cells'] += 1; continue
            population = cell['population']
            if population is None:
                counts['unknown_population_cells'] += 1; continue
            counts['newly_covered_cells'] += 1
            counts['partial_population_cells'] += cell.get('valid_pixel_fraction') is not None and cell['valid_pixel_fraction'] < 1
            residents.append(population)
            before.append(population * cell['nearest_cycleway_m'])
            after.append(population * min(cell['nearest_cycleway_m'], distance))
        population = math.fsum(residents)
        if population <= 0 or any(p[k] != v for k, v in counts.items()):
            raise ValueError('Independent population gain or known/unknown/existing coverage counts failed.')
        close(p['population_coverage_gain'], population, 'population gain')
        close(p.get('current_access_m'), math.fsum(before) / population, 'baseline weighted access')
        close(p.get('new_access_m'), math.fsum(after) / population, 'after weighted access')
        close(p['access_improvement_m'], (math.fsum(before) - math.fsum(after)) / population, 'access improvement')
        close(p['ranking_score'], population * (.5 + .5 * p['priority'] / 100) * p['routing_suitability'], 'ranking')
    if canonical(saved) != canonical(expected):
        raise ValueError('Saved output differs from complete input-derived candidates, ranking, fields or metadata.')
    print(f'Independent verification PASSED: {len(saved["features"])} corridors; directed edge continuity, access, '
          'geometry, new/total lengths, IDs, scores and independently recomputed population gains.', flush=True)


def verify_saved(path, expected, ctx):
    saved = json.loads(path.read_bytes())
    verify_document(saved, expected, ctx)
    if saved['features']:
        frame = gpd.read_file(path)
        if (frame.crs is None or frame.crs.to_epsg() != 4326 or len(frame) != len(saved['features'])
                or not frame.geom_type.isin(['LineString', 'MultiLineString']).all() or not frame.is_valid.all()
                or frame['id'].tolist() != [f['id'] for f in saved['features']]):
            raise ValueError('GeoJSON reload failed CRS/geometry/count/ID validation.')


def save_output(document, ctx, path=OUTPUT):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                prefix='.bike-recommendations-', suffix='.geojson', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(document, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        verify_saved(temporary, document, ctx)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f'Saved preliminary bicycle corridors: {path}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Recompute and verify existing output locally; no writes or network requests.')
    args = parser.parse_args()
    if args.verify_only and not OUTPUT.is_file():
        raise ValueError('No saved bicycle recommendations to verify; no files written.')
    started = perf_counter()
    ctx = load_inputs()
    report('EDGE ACCESS SCREENING', ctx['access_stats'])
    document = build_document(ctx)
    report('SCREENING', document['screening'])
    report('TOP CANDIDATE BENEFITS (STANDALONE)', [
        {k: f['properties'][k] for k in ('id', 'population_coverage_gain', 'priority', 'network_distance_m', 'new_corridor_length_m', 'routing_suitability')}
        for f in document['features'][:5]])
    if not document['features']:
        print('No useful corridors qualify. See screening and edge-access rejection counts; fixed thresholds were not relaxed.', flush=True)
    if args.verify_only:
        verify_saved(OUTPUT, document, ctx)
    else:
        save_output(document, ctx)
    print(f'Total offline runtime: {perf_counter() - started:.2f} seconds; graph was only loaded, never rebuilt or downloaded.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
