from pathlib import Path

import geopandas as gpd
import osmnx as ox


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BOUNDARY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "boundaries"
    / "baku_boundary.geojson"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "networks"
    / "baku_drive.graphml"
)


def load_boundary():
    print(f"Loading boundary: {BOUNDARY_PATH}")

    boundary_gdf = gpd.read_file(BOUNDARY_PATH)

    if boundary_gdf.empty:
        raise RuntimeError("Boundary file is empty.")

    if len(boundary_gdf) != 1:
        raise RuntimeError(
            f"Expected exactly 1 boundary feature, got {len(boundary_gdf)}."
        )

    if boundary_gdf.crs is None:
        raise RuntimeError("Boundary has no CRS.")

    boundary_gdf = boundary_gdf.to_crs("EPSG:4326")

    geometry = boundary_gdf.geometry.iloc[0]

    if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise RuntimeError(
            f"Unexpected boundary geometry: {geometry.geom_type}"
        )

    if not geometry.is_valid:
        raise RuntimeError("Boundary geometry is invalid.")

    print(f"Boundary geometry: {geometry.geom_type}")
    print(f"Boundary CRS: {boundary_gdf.crs}")

    return geometry


def download_network(boundary):
    # Keep web responses locally so reruns do not unnecessarily
    # repeat identical requests.
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(PROJECT_ROOT / "cache")

    # Show OSMnx progress in the terminal.
    ox.settings.log_console = True

    print()
    print("Downloading Baku driving network from OpenStreetMap...")
    print("Network type: drive")
    print("retain_all: True")
    print()
    print("This can take several minutes.")

    graph = ox.graph.graph_from_polygon(
        boundary,
        network_type="drive",
        simplify=True,
        retain_all=True,
    )

    if graph.number_of_nodes() == 0:
        raise RuntimeError("Downloaded graph contains no nodes.")

    if graph.number_of_edges() == 0:
        raise RuntimeError("Downloaded graph contains no edges.")

    return graph


def save_and_verify(graph):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ox.io.save_graphml(
        graph,
        filepath=OUTPUT_PATH,
    )

    # Reload immediately to prove that the saved GraphML is usable.
    loaded_graph = ox.io.load_graphml(
        filepath=OUTPUT_PATH,
    )

    if loaded_graph.number_of_nodes() != graph.number_of_nodes():
        raise RuntimeError(
            "Reloaded graph has a different node count."
        )

    if loaded_graph.number_of_edges() != graph.number_of_edges():
        raise RuntimeError(
            "Reloaded graph has a different edge count."
        )

    xs = [
        data["x"]
        for _, data in graph.nodes(data=True)
        if "x" in data
    ]

    ys = [
        data["y"]
        for _, data in graph.nodes(data=True)
        if "y" in data
    ]

    if not xs or not ys:
        raise RuntimeError(
            "Graph nodes are missing longitude/latitude coordinates."
        )

    bounds = [
        min(xs),
        min(ys),
        max(xs),
        max(ys),
    ]

    print()
    print("Driving network saved successfully.")
    print(f"Nodes:        {graph.number_of_nodes()}")
    print(f"Edges:        {graph.number_of_edges()}")
    print(f"CRS:          {graph.graph.get('crs')}")
    print(f"Bounds:       {bounds}")
    print(f"Saved to:     {OUTPUT_PATH}")
    print("Reload check: PASSED")


def main():
    boundary = load_boundary()
    graph = download_network(boundary)
    save_and_verify(graph)


if __name__ == "__main__":
    main()
