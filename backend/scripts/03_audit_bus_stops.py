"""Audit OSM-mapped bus stops; save only the raw OSMnx feature result.

OSMnx itself may repair invalid geometries during retrieval. This script
preserves its returned geometries, index and all columns without normalization.
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import osmnx as ox


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = PROJECT_ROOT / "data/processed/boundaries/baku_boundary.geojson"
OUTPUT_PATH = PROJECT_ROOT / "data/raw/osm/baku_bus_stops_raw.geojson"
TAGS = {"highway": "bus_stop"}


def load_boundary():
    print(f"Loading boundary: {BOUNDARY_PATH}", flush=True)
    boundary = gpd.read_file(BOUNDARY_PATH)
    if len(boundary) != 1:
        raise RuntimeError(f"Expected one boundary feature, got {len(boundary)}.")
    if boundary.crs is None:
        raise RuntimeError("Boundary has no CRS.")
    geometry = boundary.to_crs("EPSG:4326").geometry.iloc[0]
    if geometry is None or geometry.is_empty:
        raise RuntimeError("Boundary geometry is missing or empty.")
    if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise RuntimeError(f"Boundary must be polygonal, got {geometry.geom_type}.")
    if not geometry.is_valid:
        raise RuntimeError("Boundary geometry is invalid.")
    print(f"Boundary: {geometry.geom_type}, EPSG:4326, bounds={geometry.bounds}")
    return geometry


def download_bus_stops(boundary):
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(PROJECT_ROOT / "cache")
    ox.settings.log_console = True
    ox.settings.requests_timeout = 120
    print(f"Retrieving OSM features with tags={TAGS} ...", flush=True)
    try:
        stops = ox.features_from_polygon(boundary, tags=TAGS)
    except Exception as exc:
        # Do not turn network/service failures into a successful empty export.
        raise RuntimeError(
            "OSM bus-stop retrieval failed; no raw export was written by this run. "
            f"Check network access and the Overpass service. "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    if stops.empty:
        raise RuntimeError("OSM query returned no bus stops; no raw export written.")
    if stops.crs is None or stops.crs.to_epsg() != 4326:
        raise RuntimeError(f"Unexpected OSM result CRS: {stops.crs}; refusing to reproject.")
    return stops


def audit(stops):
    geometry = stops.geometry
    missing_geometry = geometry.isna()
    present = geometry.loc[~missing_geometry]
    if "name" in stops.columns:
        names = stops["name"]
        missing_names = names.isna() | names.map(
            lambda value: isinstance(value, str) and not value.strip()
        )
        print(f"Missing/blank names: {int(missing_names.sum())}")
    else:
        print(f"Missing names: {len(stops)} (no 'name' field returned)")

    print(f"Feature count: {len(stops)}")
    print(f"Actual geometry types: {geometry.geom_type.value_counts(dropna=False).to_dict()}")
    print(f"CRS: {stops.crs}")
    print(f"Bounds [min_lon, min_lat, max_lon, max_lat]: {stops.total_bounds.tolist()}")
    print(f"Index fields: {list(stops.index.names)}")
    print(f"Duplicate OSM index rows beyond first: {int(stops.index.duplicated().sum())}")
    # Exact WKB equality, not proximity: distinct co-located stops remain intact.
    print(f"Duplicate geometries beyond first (exact WKB): {int(present.to_wkb().duplicated().sum())}")
    print(f"Missing geometries: {int(missing_geometry.sum())}")
    print(f"Empty geometries: {int(present.is_empty.sum())}")
    print(f"Invalid non-null geometries: {int((~present.is_valid).sum())}")
    print(f"Returned fields: {list(stops.columns)}")
    print("Sample field values (up to three non-null values per field):")
    for field in stops.columns:
        if field != geometry.name:
            values = stops[field].dropna().head(3).tolist()
            print(f"  {field}: {values!r}")
    print("Sample OSM indices and original geometries:")
    print(geometry.head(5).to_string())


def save_and_verify(stops):
    # Use GeoPandas' JSON serializer rather than a driver that may coerce lists
    # or field types. Never select a fixed set of tag columns.
    document = json.loads(stops.to_json(na="null", drop_id=True))
    index_values = json.loads(stops.index.to_frame(index=False).to_json(orient="values"))
    for feature, values in zip(document["features"], index_values, strict=True):
        # GeoJSON foreign member keeps IDs separate from potentially colliding
        # OSM tags such as 'id' or 'element'. Numeric OSM IDs remain numeric.
        feature["osm_index"] = {"names": list(stops.index.names), "values": values}
        feature["id"] = "/".join(str(value) for value in values)

    serialized = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents silently overwriting an earlier raw snapshot.
    with OUTPUT_PATH.open("x", encoding="utf-8") as output:
        output.write(serialized + "\n")
    with OUTPUT_PATH.open(encoding="utf-8") as saved:
        if json.load(saved) != document:
            raise RuntimeError("Raw GeoJSON reload changed properties, IDs or geometries.")
    reloaded = gpd.read_file(OUTPUT_PATH)
    if len(reloaded) != len(stops) or reloaded.crs != stops.crs:
        raise RuntimeError("Raw GeoJSON reload changed the feature count or CRS.")
    print(f"Raw GeoJSON saved: {OUTPUT_PATH}")
    print("Reload verification: PASSED (all properties, IDs, geometries, count and CRS)")


def main():
    if OUTPUT_PATH.exists():
        raise RuntimeError(
            f"Raw output already exists: {OUTPUT_PATH}. "
            "Move it aside before rerunning to preserve the previous snapshot."
        )
    stops = download_bus_stops(load_boundary())
    audit(stops)
    save_and_verify(stops)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
