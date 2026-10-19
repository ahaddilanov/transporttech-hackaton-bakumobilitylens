"""Standardize provisional OSM stop points into an intermediate dataset.

Reject malformed records explicitly. Do not infer service, route membership or
operational status, and do not merge nearby stops with distinct OSM identifiers.
"""

import argparse
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from tempfile import NamedTemporaryFile

import geopandas as gpd
import numpy as np
from shapely.geometry import Point


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data/raw/osm/baku_bus_stops_raw.geojson"
BOUNDARY_PATH = PROJECT_ROOT / "data/processed/boundaries/baku_boundary.geojson"
OUTPUT_PATH = PROJECT_ROOT / "data/processed/transport/bus_stops.geojson"
EXPECTED_RAW_COUNT = 1414
NEAR_DUPLICATE_METERS = 5.0


def load_inputs():
    with RAW_PATH.open(encoding="utf-8") as source:
        raw = json.load(source)
    if not isinstance(raw, dict) or raw.get("type") != "FeatureCollection":
        raise RuntimeError("Raw input must be a GeoJSON FeatureCollection.")
    features = raw.get("features")
    if not isinstance(features, list) or len(features) != EXPECTED_RAW_COUNT:
        raise RuntimeError(f"Expected the audited {EXPECTED_RAW_COUNT} raw features; input count/schema changed.")
    # The actual raw file is standard longitude/latitude GeoJSON without a CRS
    # member. Reject a conflicting explicit CRS instead of guessing/reprojecting.
    if "crs" in raw:
        raise RuntimeError("Unexpected explicit raw CRS member; inspect the changed schema first.")
    fields = sorted({field for feature in features if isinstance(feature, dict)
                     and isinstance(feature.get("properties"), dict)
                     for field in feature["properties"]})
    print(f"Raw features: {len(features)}; CRS: EPSG:4326 (GeoJSON longitude/latitude)")
    print(f"Actual raw property fields: {fields}")

    boundary = gpd.read_file(BOUNDARY_PATH)
    if len(boundary) != 1 or boundary.crs is None:
        raise RuntimeError("Expected one study boundary feature with a declared CRS.")
    polygon = boundary.to_crs("EPSG:4326").geometry.iloc[0]
    if (polygon is None or polygon.is_empty or not polygon.is_valid
            or polygon.geom_type not in {"Polygon", "MultiPolygon"}):
        raise RuntimeError("Baku boundary must be a valid nonempty Polygon/MultiPolygon.")
    return features, polygon


def standardize_feature(feature, boundary):
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise ValueError("record is not a GeoJSON Feature")
    properties = feature.get("properties")
    if not isinstance(properties, dict) or properties.get("highway") != "bus_stop":
        raise ValueError("properties are missing or highway is not bus_stop")
    osm_index = feature.get("osm_index")
    if not isinstance(osm_index, dict) or osm_index.get("names") != ["element", "id"]:
        raise ValueError("missing or unexpected original osm_index.names")
    values = osm_index.get("values")
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError("osm_index.values must contain element type and OSM ID")
    element, osm_id = values
    if element not in ("node", "way", "relation"):
        raise ValueError("unrecognized OSM element type")
    if type(osm_id) is not int or osm_id <= 0:
        raise ValueError("OSM ID must be an actual positive integer")
    original_id = feature.get("id")
    if original_id != f"{element}/{osm_id}":
        raise ValueError("raw feature ID disagrees with original OSM identifiers")

    geometry = feature.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        raise ValueError("geometry is missing or is not Point; no conversion permitted")
    coordinates = geometry.get("coordinates")
    if (not isinstance(coordinates, list) or len(coordinates) != 2
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in coordinates)):
        raise ValueError("Point coordinates must be two finite numeric longitude/latitude values")
    longitude, latitude = coordinates
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        raise ValueError("longitude/latitude outside valid geographic ranges")
    point = Point(coordinates)
    if point.is_empty or not point.is_valid:
        raise ValueError("Point geometry is empty or invalid")
    # Covers includes a point exactly on the study boundary; there is no buffer.
    if not boundary.covers(point):
        raise ValueError("Point is outside the Baku study polygon")
    name = properties.get("name")
    if name is not None and not isinstance(name, str):
        raise ValueError("name must be a string or null")
    if isinstance(name, str) and not name.strip():
        name = None

    identifier = f"osm:{element}:{osm_id}"
    return {
        "type": "Feature", "id": identifier,
        "properties": {
            "id": identifier, "name": name, "source": "OpenStreetMap",
            "osm_element": element, "osm_id": osm_id,
            "osm_feature_id": original_id,
        },
        "osm_index": osm_index,
        "geometry": {"type": "Point", "coordinates": coordinates},
    }


def process_features(features, boundary):
    accepted, failures = [], []
    for row, feature in enumerate(features, start=1):
        try:
            accepted.append(standardize_feature(feature, boundary))
        except ValueError as exc:
            failures.append({"input_row_1_based": row,
                             "raw_id": feature.get("id") if isinstance(feature, dict) else None,
                             "reason": str(exc)})
    print(f"Validation failures/excluded records: {len(failures)}")
    for failure in failures:
        print("EXCLUDED: " + json.dumps(failure, ensure_ascii=False))
    if not accepted:
        raise RuntimeError("No valid stops remain; no processed output written.")
    if len(accepted) + len(failures) != len(features):
        raise RuntimeError("Input/output count accounting failed.")
    repeated = [identifier for identifier, count in
                Counter(f["id"] for f in accepted).items() if count > 1]
    if repeated:
        raise RuntimeError(f"Duplicate OSM-derived IDs: {repeated}; refusing arbitrary deduplication or invented IDs.")
    print(f"Input/accepted/excluded: {len(features)}/{len(accepted)}/{len(failures)}")
    return {"type": "FeatureCollection", "features": accepted}


def report_spatial_checks(document):
    features = document["features"]
    points = gpd.GeoSeries([Point(f["geometry"]["coordinates"]) for f in features], crs="EPSG:4326")
    metric = points.to_crs("EPSG:32639")
    xy = np.column_stack([metric.x, metric.y])
    exact_pairs = nearby_pairs = 0
    # Small audited input: vectorize comparisons, without adding a dependency.
    for i in range(len(features)):
        squared = np.square(xy[i + 1:] - xy[i]).sum(axis=1)
        for offset in np.flatnonzero(squared <= NEAR_DUPLICATE_METERS ** 2):
            j = i + 1 + int(offset)
            exact = features[i]["geometry"]["coordinates"] == features[j]["geometry"]["coordinates"]
            exact_pairs += int(exact)
            nearby_pairs += 1
            print(f"SPATIAL REVIEW: {features[i]['id']} / {features[j]['id']}; "
                  f"distance={math.sqrt(float(squared[offset])):.3f} m; exact_coordinates={exact}")
    print(f"Possible spatial duplicate pairs within {NEAR_DUPLICATE_METERS} m (EPSG:32639): {nearby_pairs}")
    print(f"Exact-coordinate pairs: {exact_pairs}; all distinct OSM IDs retained")
    print(f"Output Point count / unique IDs: {len(features)} / {len({f['id'] for f in features})}")
    print(f"Missing names (JSON null): {sum(f['properties']['name'] is None for f in features)}")
    print(f"Boundary-covered output count: {len(features)} (validated with covers, no buffer)")
    print(f"CRS: EPSG:4326; bounds [west, south, east, north]: {points.total_bounds.tolist()}")


def verify_saved(path, expected):
    with path.open(encoding="utf-8") as source:
        saved = json.load(source)
    if saved != expected:
        raise RuntimeError("Saved output differs from validated raw-derived features, names or identifiers.")
    reloaded = gpd.read_file(path)
    if (len(reloaded) != len(expected["features"]) or reloaded.crs.to_epsg() != 4326
            or not reloaded.geom_type.eq("Point").all() or not reloaded.is_valid.all()):
        raise RuntimeError("GeoJSON reload failed count, CRS or Point-geometry validation.")
    print("Reload verification: PASSED (JSON preservation, count, CRS and valid Points)")


def save_output(document):
    serialized = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=OUTPUT_PATH.parent,
                                prefix=".bus-stops-", suffix=".geojson", delete=False) as output:
            temporary_path = Path(output.name)
            output.write(serialized + "\n")
            output.flush()
            os.fsync(output.fileno())
        verify_saved(temporary_path, document)
        os.replace(temporary_path, OUTPUT_PATH)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    print(f"Processed intermediate file saved: {OUTPUT_PATH}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Validate saved output against raw inputs without writing.")
    args = parser.parse_args()
    features, boundary = load_inputs()
    document = process_features(features, boundary)
    report_spatial_checks(document)
    if args.verify_only:
        verify_saved(OUTPUT_PATH, document)
    else:
        save_output(document)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
