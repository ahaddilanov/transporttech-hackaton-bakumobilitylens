"""Offline synthetic checks for Step 16B-1; never query OSM."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, MultiPolygon, Polygon, box, mapping
import shapely

SPEC = importlib.util.spec_from_file_location('bike_network', Path(__file__).resolve().parents[1] / 'scripts/15_build_bike_network.py')
bike = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bike)


def fixture():
    graph = nx.MultiDiGraph(crs='EPSG:32639', simplified=False)
    for node, x in [(1, 400000), (2, 400100), (3, 410000), (4, 410100)]:
        lon, lat = bike.TO_GEO(x, 4470000)
        graph.add_node(node, x=x, y=4470000., lon=lon, lat=lat)
    for u, v, way in [(1, 2, 10), (2, 1, 10), (3, 4, 20)]:
        geometry = LineString([(graph.nodes[u]['x'], 4470000), (graph.nodes[v]['x'], 4470000)])
        tags = {'highway': 'residential', 'bicycle': 'yes', 'oneway': 'no' if way == 10 else 'yes'}
        graph.add_edge(u, v, osmid=way, length=100., length_utm_m=100., geometry=geometry,
                       highway='residential', bicycle='yes', oneway=way == 20,
                       osm_tags_json=bike.canonical(tags))
    area = MultiPolygon([box(399900, 4469900, 400200, 4470100), box(409900, 4469900, 410200, 4470100)])
    return graph, area


class BikeNetworkTests(unittest.TestCase):
    def test_exact_intersection_accepts_only_negligible_floating_point_boundary_error(self):
        boundary = Polygon([(400319.4567344631, 4470186.198771363),
                            (405273.8722328548, 4470031.394487486),
                            (403029.80058498314, 4477102.97935641)])
        line = LineString([(398340.1999865909, 4471213.796152835),
                           (398157.0735851884, 4474292.780931754)])
        area = bike.make_study_area([line], boundary)
        self.assertTrue(area.is_valid)
        expected = line.buffer(3000, quad_segs=16).intersection(boundary)
        self.assertTrue(area.equals_exact(expected, tolerance=0))
        self.assertLessEqual(area.difference(boundary).area, 1e-6)

    def test_buffers_dissolve_clip_and_preserve_disconnected_parts(self):
        lines = [LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)]),
                 LineString([(20000, 0), (20100, 0)])]
        boundary = box(-1000, -1000, 25000, 1000)
        area = bike.make_study_area(lines, boundary)
        self.assertTrue(area.is_valid)
        self.assertEqual(len(area.geoms), 2)
        self.assertTrue(boundary.covers(area))
        self.assertAlmostEqual(area.bounds[0], -1000)
        # Recompute each point on the 3,000m extent, rather than a degree buffer.
        self.assertTrue(area.covers(box(-999, -999, 200, 999)))

    def test_validate_retains_both_components_and_direction(self):
        graph, area = fixture()
        summary = bike.validate_graph(graph, area)
        self.assertEqual(summary['nodes'], 4)
        self.assertEqual(summary['edges'], 3)
        self.assertEqual(summary['weak_component_node_sizes'], [2, 2])
        self.assertEqual(summary['strong_component_count'], 3)
        self.assertEqual(summary['oneway_directed_edges'], 1)
        self.assertEqual(summary['highway_directed_edge_counts'], {'residential': 3})

    def test_component_histogram_survives_json_roundtrip_without_key_reordering(self):
        graph, area = fixture()
        for i in range(10):
            x, y = 400000 + 10 * i, 4470050.
            lon, lat = bike.TO_GEO(x, y)
            graph.add_node(100 + i, x=x, y=y, lon=lon, lat=lat)
        for i in range(10):
            u, v = 100 + i, 100 + (i + 1) % 10
            geometry = LineString([(graph.nodes[u]['x'], graph.nodes[u]['y']),
                                   (graph.nodes[v]['x'], graph.nodes[v]['y'])])
            graph.add_edge(u, v, osmid=50, length=geometry.length,
                           length_utm_m=geometry.length, geometry=geometry,
                           highway='path', oneway=True,
                           osm_tags_json=bike.canonical({'highway': 'path', 'oneway': 'yes'}))
        summary = bike.validate_graph(graph, area)
        self.assertEqual(bike.canonical(summary), bike.canonical(json.loads(json.dumps(summary))))

    def test_bad_nodes_lengths_geometry_and_direction_fail(self):
        for defect in ('nan_node', 'outside', 'length', 'geometry', 'undirected', 'tags'):
            with self.subTest(defect=defect):
                graph, area = fixture()
                if defect == 'nan_node': graph.nodes[1]['x'] = float('nan')
                elif defect == 'outside': graph.nodes[1]['x'] = 300000
                elif defect == 'length': graph.edges[1, 2, 0]['length'] = -1
                elif defect == 'geometry': graph.edges[1, 2, 0]['geometry'] = LineString([(0, 0), (1, 1)])
                elif defect == 'undirected': graph = nx.MultiGraph(graph)
                else: graph.edges[1, 2, 0]['osm_tags_json'] = '{}'
                with self.assertRaises(ValueError): bike.validate_graph(graph, area)

    def test_overpass_remarks_and_missing_referenced_nodes_fail(self):
        with self.assertRaisesRegex(ValueError, 'remark'):
            bike.audit_responses([{'remark': 'runtime error: Query timed out', 'elements': []}])
        with self.assertRaisesRegex(ValueError, 'missing'):
            bike.audit_responses([{'elements': [{'type': 'way', 'id': 1, 'nodes': [7, 8], 'tags': {'highway': 'path'}}]}])

    def test_graphml_roundtrip_preserves_attributes_and_offline_verification(self):
        graph, area = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bike.graphml'
            ox.save_graphml(graph, path)
            before = (path.read_bytes(), path.stat().st_mtime_ns)
            with patch('requests.sessions.Session.request', side_effect=AssertionError('OSM access forbidden')):
                loaded = bike.load_graph(path)
                bike.validate_graph(loaded, area)
                bike.verify_roundtrip(graph, loaded)
            self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))
            changed = copy.deepcopy(loaded)
            changed.edges[1, 2, 0]['bicycle'] = 'no'
            with self.assertRaises(ValueError): bike.verify_roundtrip(graph, changed)

    def test_complete_output_pair_verifies_offline_and_rejects_missing_area_part(self):
        graph, area = fixture()
        geographic = shapely.transform(area, bike.TO_GEO, interleaved=False)
        base = {'method_version': bike.METHOD}
        provenance = {**base, 'all_responses_validated': True, 'network_type': 'bike',
                      'retain_all': True, 'simplify': False, 'response_count': 1,
                      'expected_response_count': 1, 'download_seconds': 1.0,
                      'retrieved_at_utc': '2026-10-16T00:00:00+00:00', 'osm_base_timestamps': []}
        graph.graph['bike_provenance_json'] = bike.canonical(provenance)
        with tempfile.TemporaryDirectory() as folder:
            graph_path, area_path = Path(folder) / 'bike.graphml', Path(folder) / 'area.geojson'
            ox.save_graphml(graph, graph_path)
            doc = {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
                   'properties': {'id': 'baku:bike-study-area:3000m'}, 'geometry': mapping(geographic)}],
                   'metadata': {**provenance, 'graphml_sha256': bike.digest(graph_path),
                                'validation_summary': bike.validate_graph(graph, area)}}
            area_path.write_text(json.dumps(doc))
            before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (area_path, graph_path)]
            with patch('requests.sessions.Session.request', side_effect=AssertionError('OSM access forbidden')):
                bike.verify_outputs(area, geographic, base, area_path, graph_path)
            self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in (area_path, graph_path)])
            doc['features'][0]['geometry'] = mapping(geographic.geoms[0])
            area_path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                bike.verify_outputs(area, geographic, base, area_path, graph_path)


if __name__ == '__main__':
    unittest.main()
