"""Synthetic/offline corridor checks: no Baku files or OSM requests required."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx
import numpy as np
import shapely
from shapely.geometry import LineString, Point, box

SPEC = importlib.util.spec_from_file_location('bike_rec', Path(__file__).resolve().parents[1] / 'scripts/16_recommend_bike_corridors.py')
rec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rec)


def edge(highway='residential', **changes):
    tags = {'highway': highway, 'bicycle': 'yes', 'surface': 'asphalt', 'maxspeed': '30', 'lit': 'yes'}
    tags.update(changes)
    return {'osm_tags_json': tags, 'oneway': False, 'reversed': False}


def graph_fixture():
    graph = nx.MultiDiGraph(crs='EPSG:32639')
    for node, x in [(1, 400000), (2, 400300), (3, 400600), (4, 400900), (5, 402000), (6, 402500)]:
        graph.add_node(node, x=x, y=4470000.)
    for u, v in [(1, 2), (2, 3), (3, 4), (5, 6)]:
        for start, end in [(u, v), (v, u)]:
            geometry = LineString([(graph.nodes[start]['x'], 4470000), (graph.nodes[end]['x'], 4470000)])
            graph.add_edge(start, end, **edge(), geometry=geometry,
                           length_utm_m=geometry.length, length=geometry.length, osmid=u)
    return graph


class PolicyTests(unittest.TestCase):
    def test_explicit_access_private_busway_trunk_and_conditional_exclusions(self):
        for data in [edge(bicycle='no'), edge(access='private'), edge(access='no'),
                     edge('busway', bicycle=None), edge('trunk'), edge('trunk_link'),
                     edge('service', service='parking_aisle'), edge(**{'bicycle:conditional': 'yes @ (Mo-Fr)'}),
                     edge('primary', maxspeed='80'), edge('path', bicycle=None),
                     edge(**{'bicycle:forward': 'dismount'}), edge(**{'oneway:bicycle': 'reversible'})]:
            with self.subTest(data=data):
                self.assertIsNotNone(rec.edge_policy(data)['rejection'])

    def test_cost_favors_cycleways_and_residential_over_uncertain_service(self):
        cycle = rec.edge_policy(edge('cycleway'))
        residential = rec.edge_policy(edge())
        service = rec.edge_policy(edge('service', surface=None, maxspeed=None, lit=None))
        self.assertLess(cycle['factor'], residential['factor'])
        self.assertLess(residential['factor'], service['factor'])
        self.assertIn('unknown_surface', service['flags'])
        self.assertIn('uncertain_service_road', service['flags'])

    def test_no_invented_reverse_edges_or_connections_between_components(self):
        graph = graph_fixture()
        graph.remove_edge(2, 1, 0)
        routing, _ = rec.build_routing_graph(graph)
        _, paths = rec.route_search(routing, [2])
        self.assertNotIn(1, paths)
        self.assertNotIn(5, paths)
        self.assertEqual(paths[4], [2, 3, 4])

    def test_directional_bicycle_prohibition_and_barrier_rejection(self):
        backward = edge(**{'bicycle:backward': 'no'})
        backward['reversed'] = True
        self.assertIsNotNone(rec.edge_policy(backward)['rejection'])
        graph = graph_fixture()
        graph.nodes[2]['barrier'] = 'gate'
        routing, stats = rec.build_routing_graph(graph)
        _, paths = rec.route_search(routing, [1])
        self.assertNotIn(3, paths)
        self.assertGreater(stats['node_access_rejections'], 0)

    def test_parallel_edge_choice_and_routing_are_stable(self):
        graph = graph_fixture()
        data = copy.deepcopy(graph.edges[1, 2, 0])
        data['osm_tags_json'] = edge('service', surface=None)['osm_tags_json']
        graph.add_edge(1, 2, key=3, **data)
        routing, _ = rec.build_routing_graph(graph)
        self.assertEqual(routing[1][2]['edge_key'], 0)
        _, paths = rec.route_search(routing, [1])
        trace, edges = rec.trace_path(graph, routing, paths[4])
        self.assertEqual(edges, [(1, 2, 0), (2, 3, 0), (3, 4, 0)])
        self.assertEqual(trace.length, 900)
        with self.assertRaises(ValueError):
            rec.trace_path(graph, routing, [1, 5])


class GeometryCoverageTests(unittest.TestCase):
    def test_existing_infrastructure_is_removed_from_new_geometry(self):
        line = LineString([(0, 0), (1000, 0)])
        proposed = rec.proposed_geometry(line, box(-10, -10, 300, 10))
        self.assertEqual(proposed.length, 700)
        self.assertTrue(rec.classify_existing({'highway': 'cycleway'}))
        self.assertTrue(rec.classify_existing({'cycleway:right': 'lane'}))
        self.assertFalse(rec.classify_existing({'bicycle': 'yes', 'highway': 'residential'}))

    def test_complete_geometry_population_and_unknowns_not_endpoint_or_existing_osm(self):
        origins = np.array([Point(500, 100), Point(500, 300), Point(500, 100), Point(500, 100), Point(500, 100)])
        props = [{'population': p, 'nearest_cycleway_m': b, 'valid_pixel_fraction': 1}
                 for p, b in [(100, 900), (300, 800), (None, 900), (1000, 500), (5000, 900)]]
        ctx = {'origins': origins, 'props': props, 'origin_tree': shapely.STRtree(origins),
               'existing_osm_distances': np.array([1000, 1000, 1000, 1000, 200])}
        result = rec.coverage(LineString([(0, 0), (1000, 0)]), ctx)
        self.assertEqual(result['population_coverage_gain'], 400)
        self.assertEqual(result['newly_covered_cells'], 2)
        self.assertEqual(result['unknown_population_cells'], 1)
        self.assertEqual(result['existing_osm_coverage_excluded_cells'], 1)
        self.assertEqual(result['current_access_m'], 825)
        self.assertEqual(result['new_access_m'], 250)
        self.assertEqual(result['access_improvement_m'], 575)

    def test_thresholds_zero_population_and_existing_coverage_are_conservative(self):
        origins = np.array([Point(500, 500), Point(500, 500.01), Point(500, 0)])
        ctx = {'origins': origins, 'origin_tree': shapely.STRtree(origins),
               'props': [{'population': p, 'nearest_cycleway_m': b} for p, b in [(20, 501), (100, 900), (0, 900)]],
               'existing_osm_distances': np.array([501, 1000, 1000])}
        self.assertEqual(rec.coverage(LineString([(0, 0), (1000, 0)]), ctx)['population_coverage_gain'], 20)
        ctx['existing_osm_distances'][0] = 500
        self.assertEqual(rec.coverage(LineString([(0, 0), (1000, 0)]), ctx)['population_coverage_gain'], 0)

    def test_overlap_and_length_cutoffs(self):
        a = LineString([(0, 0), (1000, 0)])
        self.assertTrue(rec.substantially_overlaps(a, LineString([(0, 10), (700, 10)])))
        self.assertFalse(rec.substantially_overlaps(a, LineString([(0, 500), (1000, 500)])))
        self.assertTrue(rec.valid_lengths(200, 4000))
        self.assertFalse(rec.valid_lengths(199.99, 1000))
        self.assertFalse(rec.valid_lengths(300, 4000.01))


def full_context():
    graph = graph_fixture()
    origins = np.array([Point(400900, 4470050), Point(400450, 4470100), Point(400700, 4470100)], dtype=object)
    props = [{'id': f'grid:{i}', 'population': population, 'bike_priority': priority,
              'nearest_cycleway_m': distance, 'valid_pixel_fraction': 1., 'scoring_model_version': 'test-v1'}
             for i, (population, priority, distance) in enumerate([(200, 70, 900), (300, 10, 700), (None, None, 800)])]
    return rec.prepare_context(graph, box(399000, 4469000, 403000, 4471000),
                               [{'id': 'ayna:1', 'name': 'Existing lane'}],
                               np.array([LineString([(400000, 4469900), (400000, 4470100)])]),
                               props, origins,
                               [{'id': 'school:1', 'name': 'Example school', 'category': 'SCHOOL'}],
                               np.array([Point(400900, 4470000)]), {})


class CompleteProposalTests(unittest.TestCase):
    def test_export_uses_real_directed_path_new_geometry_and_known_population(self):
        ctx = full_context()
        doc = rec.build_document(ctx)
        self.assertEqual(len(doc['features']), 1)
        p = doc['features'][0]['properties']
        self.assertEqual(p['priority'], 70)
        self.assertEqual(p['end_name'], 'Example school')
        self.assertEqual(p['population_coverage_gain'], 500)
        self.assertEqual(p['unknown_population_cells'], 1)
        self.assertAlmostEqual(p['network_distance_m'], 900)
        self.assertAlmostEqual(p['new_corridor_length_m'], 875, places=5)
        self.assertEqual(p['route_edges'], [[1, 2, 0], [2, 3, 0], [3, 4, 0]])
        rec.verify_document(doc, doc, ctx)

    def test_identical_inputs_stable_ids_and_reordering_grid_does_not_change_result(self):
        ctx = full_context()
        doc = rec.build_document(ctx)
        ctx['props'].reverse(); ctx['origins'] = ctx['origins'][::-1]
        ctx['existing_osm_distances'] = ctx['existing_osm_distances'][::-1]
        ctx['origin_tree'] = shapely.STRtree(ctx['origins'])
        self.assertEqual(doc, rec.build_document(ctx))

    def test_no_routes_when_components_or_eligibility_block_target(self):
        ctx = full_context()
        ctx['routing'].remove_edge(2, 3)
        doc = rec.build_document(ctx)
        self.assertEqual(doc['features'], [])
        self.assertEqual(doc['screening']['routing_failures'], 1)

    def test_verifier_independently_rejects_gains_geometry_ids_scores_and_route_jumps(self):
        ctx = full_context()
        original = rec.build_document(ctx)
        for field, value in [('population_coverage_gain', 9999), ('priority', 101), ('id', 'bad'),
                             ('network_distance_m', 5000), ('route_edges', [[1, 2, 0], [3, 4, 0]])]:
            with self.subTest(field=field):
                doc = copy.deepcopy(original); doc['features'][0]['properties'][field] = value
                with self.assertRaises(ValueError): rec.verify_document(doc, doc, ctx)
        doc = copy.deepcopy(original)
        doc['features'][0]['geometry'] = {'type': 'LineString', 'coordinates': [[0, 0], [1, 1]]}
        with self.assertRaises(ValueError): rec.verify_document(doc, doc, ctx)

    def test_save_and_verify_are_offline_and_do_not_overwrite_during_verification(self):
        ctx = full_context(); doc = rec.build_document(ctx)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'recommendations.geojson'
            with patch('requests.sessions.Session.request', side_effect=AssertionError('network forbidden')):
                rec.save_output(doc, ctx, path)
                before = (path.read_bytes(), path.stat().st_mtime_ns)
                rec.verify_saved(path, doc, ctx)
            self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_existing_osm_near_target_prevents_false_new_coverage(self):
        ctx = full_context()
        ctx['existing_osm_distances'][:] = 0
        doc = rec.build_document(ctx)
        self.assertEqual(doc['features'], [])
        self.assertEqual(doc['screening']['zero_gain_rejections'], 1)

    def test_no_ayna_anchors_produces_verified_empty_result(self):
        ctx = full_context(); ctx['anchors'] = {}
        doc = rec.build_document(ctx)
        self.assertEqual(doc['features'], [])
        self.assertEqual(doc['screening']['routing_failures'], 1)
        rec.verify_document(doc, doc, ctx)

    def test_at_most_fifteen_distinct_proposals_and_benefit_ranking(self):
        graph, lane_props, lanes, props, origins = nx.MultiDiGraph(crs='EPSG:32639'), [], [], [], []
        for i in range(20):
            y, nodes = 4470000 + i * 1500, [i * 10 + j for j in range(4)]
            for j, node in enumerate(nodes):
                graph.add_node(node, x=400000 + j * 300, y=y)
            for u, v in zip(nodes, nodes[1:]):
                geometry = LineString([(graph.nodes[u]['x'], y), (graph.nodes[v]['x'], y)])
                graph.add_edge(u, v, **edge(), geometry=geometry, length_utm_m=300, length=300, osmid=u)
            lane_props.append({'id': f'ayna:{i}', 'name': None})
            lanes.append(LineString([(400000, y - 100), (400000, y + 100)]))
            props.append({'id': f'grid:{i}', 'population': 100 + i, 'bike_priority': 70,
                          'nearest_cycleway_m': 900, 'scoring_model_version': 'test-v1'})
            origins.append(Point(400900, y))
        ctx = rec.prepare_context(graph, box(399000, 4469000, 402000, 4500000),
                                  lane_props, np.array(lanes), props, np.array(origins), [], np.array([], dtype=object), {})
        doc = rec.build_document(ctx)
        self.assertEqual(len(doc['features']), 15)
        self.assertEqual(doc['screening']['qualified_beyond_limit'], 5)
        self.assertEqual(doc['screening']['duplicate_corridors'], 0)
        self.assertEqual(doc['features'][0]['properties']['source_grid_id'], 'grid:19')
        rec.verify_document(doc, doc, ctx)


if __name__ == '__main__':
    unittest.main()
