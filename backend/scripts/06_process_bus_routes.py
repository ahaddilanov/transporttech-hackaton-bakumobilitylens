"""Process AYNA KMZ placemarks without merging labels or inferring service.

One output feature per source placemark; all its line parts stay together.
IDs prefer globally unique source FID, then globally unique KML placemark ID.
Fallback IDs are SHA-256 of member, one-based placemark position, source
attributes, label and coordinates: deterministic for identical source contents,
but not an official identifier and not invariant to source reordering.

KML coordinates are WGS84 longitude, latitude, optional altitude. Output is
two-dimensional EPSG:4326. Nonzero altitude omission is explicitly flagged.
Invalid records abort the run after reporting; suspicious valid routes remain.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, MultiLineString, mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data/raw/ayna/buslines(1).kmz"
BOUNDARY_PATH = PROJECT_ROOT / "data/processed/boundaries/baku_boundary.geojson"
OUTPUT_PATH = PROJECT_ROOT / "data/processed/transport/bus_routes.geojson"
KML_NAMESPACE = "http://www.opengis.net/kml/2.2"
NS = {"k": KML_NAMESPACE}
LONG_SEGMENT_METERS = 1000.0
SHORT_ROUTE_METERS = 10.0


class DescriptionRows(HTMLParser):
    """Read the actual nested HTML table without executing HTML or scripts."""

    def __init__(self):
        super().__init__()
        self.rows, self.row_stack, self.cell_stack = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row_stack.append([])
        elif tag == "td":
            self.cell_stack.append([])

    def handle_data(self, data):
        if self.cell_stack:
            self.cell_stack[-1].append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell_stack:
            value = "".join(self.cell_stack.pop()).strip()
            if self.row_stack:
                self.row_stack[-1].append(value)
        elif tag == "tr" and self.row_stack:
            row = self.row_stack.pop()
            if len(row) == 2:
                self.rows.append(row)


def read_kmz(path):
    records, line_count = [], 0
    with ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".kml")]
        print(f"KMZ members: {archive.namelist()}")
        if not members:
            raise RuntimeError("KMZ contains no KML document.")
        for member in members:
            # Parse in memory: never extract or modify the raw archive.
            root = ET.fromstring(archive.read(member))
            if root.tag != f"{{{KML_NAMESPACE}}}kml":
                raise RuntimeError(f"Unsupported KML root/namespace in {member}: {root.tag}")
            for position, placemark in enumerate(root.findall(".//k:Placemark", NS), start=1):
                parser = DescriptionRows()
                parser.feed(placemark.findtext("k:description", default="", namespaces=NS))
                attributes = {}
                for key, value in parser.rows:
                    if key in attributes and attributes[key] != value:
                        raise RuntimeError(f"Conflicting HTML attribute {key!r} in {member}, placemark {position}")
                    attributes[key] = value
                lines = placemark.findall(".//k:LineString", NS)
                line_count += len(lines)
                records.append({
                    "member": member, "position": position,
                    "label": placemark.findtext("k:name", namespaces=NS),
                    "kml_id": placemark.get("id"), "attributes": attributes,
                    "placemark": placemark, "lines": lines,
                })
    if not records:
        raise RuntimeError("No source placemarks found.")
    print(f"Source placemarks / LineString parts: {len(records)} / {line_count}")
    print(f"Actual HTML attribute keys: {sorted({key for r in records for key in r['attributes']})}")
    print("Source CRS: KML 2.2 WGS84 longitude/latitude; no projected-coordinate conversion")
    return records, line_count


def load_boundary():
    frame = gpd.read_file(BOUNDARY_PATH)
    if len(frame) != 1 or frame.crs is None:
        raise RuntimeError("Expected one Baku boundary with a declared CRS.")
    polygon = frame.to_crs("EPSG:4326").geometry.iloc[0]
    if (polygon is None or polygon.is_empty or not polygon.is_valid
            or polygon.geom_type not in {"Polygon", "MultiPolygon"}):
        raise RuntimeError("Baku boundary is missing, empty, invalid or non-polygonal.")
    return polygon


def parse_geometry(record):
    unsupported = {"Point", "Polygon", "LinearRing", "Model", "Track", "MultiTrack"}
    if any(element.tag.rsplit("}", 1)[-1] in unsupported for element in record["placemark"].iter()):
        raise ValueError("unsupported/non-line geometry present; refusing to discard it")
    if not record["lines"]:
        raise ValueError("placemark has no LineString parts")
    parts, nonzero_altitude = [], False
    for line in record["lines"]:
        coordinates = []
        for token in line.findtext("k:coordinates", default="", namespaces=NS).split():
            values = [float(value) for value in token.split(",")]
            if len(values) not in (2, 3) or not all(math.isfinite(value) for value in values):
                raise ValueError("coordinates must have finite longitude/latitude and optional altitude")
            longitude, latitude = values[:2]
            if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                raise ValueError("coordinates outside longitude/latitude ranges")
            nonzero_altitude |= len(values) == 3 and values[2] != 0
            coordinates.append([longitude, latitude])
        if len(coordinates) < 2:
            raise ValueError("empty LineString or fewer than two vertices")
        part = LineString(coordinates)
        if part.is_empty or not part.is_valid or part.length == 0:
            raise ValueError("empty, invalid or zero-length line part")
        parts.append(coordinates)
    geometry = LineString(parts[0]) if len(parts) == 1 else MultiLineString(parts)
    if not geometry.is_valid or geometry.is_empty:
        raise ValueError("invalid/empty route geometry")
    return geometry, nonzero_altitude


def assign_identifier(record, geometry, fid_counts, kml_counts):
    fid, kml_id = record["attributes"].get("FID"), record["kml_id"]
    if fid and fid_counts[fid] == 1:
        return f"ayna:buslines:fid:{fid}", "unique_source_FID"
    if kml_id and kml_counts[kml_id] == 1:
        return f"ayna:buslines:kml:{kml_id}", "unique_KML_placemark_id"
    payload = {"member": record["member"], "position": record["position"],
               "label": record["label"], "attributes": record["attributes"],
               "geometry": mapping(geometry)}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                       allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"ayna:buslines:sha256:{digest}", "content_and_source_position_SHA256"


def build_document(records, source_line_count, boundary):
    fid_counts = Counter(r["attributes"].get("FID") for r in records)
    kml_counts = Counter(r["kml_id"] for r in records)
    features, geometries, failures = [], [], []
    for record in records:
        try:
            geometry, nonzero_altitude = parse_geometry(record)
            identifier, scheme = assign_identifier(record, geometry, fid_counts, kml_counts)
            label = record["label"]
            name = label if label is not None and label.strip() else None
            flags = []
            if name is None:
                flags.append("missing_name")
            if not geometry.is_simple:
                flags.append("self_intersection_or_non_simple")
            if not boundary.intersects(geometry):
                flags.append("outside_study_polygon")
            elif not boundary.covers(geometry):
                flags.append("partly_outside_study_polygon")
            if nonzero_altitude:
                flags.append("nonzero_altitude_omitted_for_2D_output")
            if record["attributes"].get("Name") not in (None, label):
                flags.append("HTML_Name_differs_from_KML_label")
            features.append({
                "type": "Feature", "id": identifier,
                "properties": {
                    "id": identifier, "name": name,
                    # The actual KML label is the route reference; no parsing,
                    # demand join, direction inference or label-based grouping.
                    "route_ref": name, "avg_daily_validations": None, "source": "AYNA",
                    "source_route_label": label, "source_fid": record["attributes"].get("FID"),
                    "source_placemark_id": record["kml_id"], "source_kml_member": record["member"],
                    "source_placemark_position": record["position"],
                    "source_attributes": record["attributes"], "id_scheme": scheme,
                    "validation_flags": flags,
                },
                "geometry": mapping(geometry),
            })
            geometries.append(geometry)
        except ValueError as exc:
            failures.append({"member": record["member"], "position": record["position"],
                             "label": record["label"], "reason": str(exc)})
    print(f"Source / valid / invalid placemarks: {len(records)} / {len(features)} / {len(failures)}")
    for failure in failures:
        print("INVALID: " + json.dumps(failure, ensure_ascii=False))
    if len(features) + len(failures) != len(records):
        raise RuntimeError("Placemark count reconciliation failed.")
    if failures:
        raise RuntimeError("Invalid source placemarks reported; output not written or replaced. No records silently dropped.")
    identifiers = [feature["id"] for feature in features]
    if len(set(identifiers)) != len(identifiers):
        raise RuntimeError("Generated IDs are not unique; no output written.")
    output_parts = sum(len(g.geoms) if g.geom_type == "MultiLineString" else 1 for g in geometries)
    if output_parts != source_line_count:
        raise RuntimeError("Line-part count reconciliation failed.")

    frame = gpd.GeoSeries(geometries, crs="EPSG:4326")
    metric = frame.to_crs("EPSG:32639")
    seen = {}
    duplicate_pairs = []
    for feature, geometry, projected in zip(features, geometries, metric, strict=True):
        flags = feature["properties"]["validation_flags"]
        parts = list(projected.geoms) if projected.geom_type == "MultiLineString" else [projected]
        max_segment = max(float(np.linalg.norm(np.diff(np.asarray(part.coords), axis=0), axis=1).max()) for part in parts)
        if max_segment > LONG_SEGMENT_METERS:
            flags.append("segment_over_1000m")
        if projected.length < SHORT_ROUTE_METERS:
            flags.append("route_length_under_10m")
        if geometry.wkb in seen:
            flags.append("exact_geometry_duplicate")
            previous_flags = seen[geometry.wkb]["properties"]["validation_flags"]
            if "exact_geometry_duplicate" not in previous_flags:
                previous_flags.append("exact_geometry_duplicate")
            duplicate_pairs.append([seen[geometry.wkb]["id"], feature["id"]])
        else:
            seen[geometry.wkb] = feature
    labels = Counter(f["properties"]["name"] for f in features)
    flag_counts = Counter(flag for f in features for flag in set(f["properties"]["validation_flags"]))
    print(f"Output features / unique IDs / preserved line parts: {len(features)} / {len(set(identifiers))} / {output_parts}")
    print(f"Geometry types: {dict(Counter(g.geom_type for g in geometries))}")
    print(f"Missing names: {labels.get(None, 0)}; repeated labels retained: {dict((k, v) for k, v in labels.items() if v > 1)}")
    print(f"Boundary fully covered / partial / outside: "
          f"{sum(boundary.covers(g) for g in geometries)} / "
          f"{sum(boundary.intersects(g) and not boundary.covers(g) for g in geometries)} / "
          f"{sum(not boundary.intersects(g) for g in geometries)}")
    print(f"Suspicious valid geometry/metadata flags (retained): {dict(flag_counts)}")
    print(f"Exact geometry duplicate pairs (retained): {duplicate_pairs}")
    print("Review identifiers are preserved with validation_flags in each output feature.")
    print(f"ID schemes: {dict(Counter(f['properties']['id_scheme'] for f in features))}")
    print(f"CRS: EPSG:4326; bounds [west, south, east, north]: {frame.total_bounds.tolist()}")
    # Mapping tuples become JSON arrays, ensuring exact reload comparison.
    return json.loads(json.dumps({"type": "FeatureCollection", "features": features}, allow_nan=False))


def verify_saved(path, expected):
    with path.open(encoding="utf-8") as source:
        if json.load(source) != expected:
            raise RuntimeError("Reloaded JSON differs from source-derived geometries, labels or identifiers.")
    frame = gpd.read_file(path)
    if (len(frame) != len(expected["features"]) or frame.crs is None or frame.crs.to_epsg() != 4326
            or not frame.geom_type.isin(["LineString", "MultiLineString"]).all()
            or not frame.is_valid.all() or frame.is_empty.any()):
        raise RuntimeError("Reload failed count, CRS or geometry validation.")
    print("Reload verification: PASSED (all properties, geometry, counts and EPSG:4326)")


def save_output(document):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=OUTPUT_PATH.parent,
                                prefix=".bus-routes-", suffix=".geojson", delete=False) as output:
            temporary = Path(output.name)
            json.dump(document, output, ensure_ascii=False, allow_nan=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        verify_saved(temporary, document)
        os.replace(temporary, OUTPUT_PATH)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f"Processed intermediate routes saved: {OUTPUT_PATH}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Rebuild expected features and verify saved output without writing.")
    args = parser.parse_args()
    records, line_count = read_kmz(RAW_PATH)
    document = build_document(records, line_count, load_boundary())
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
