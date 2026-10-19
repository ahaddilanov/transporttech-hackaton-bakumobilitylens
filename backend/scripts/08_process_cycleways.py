"""Process AYNA cycleway linework as an intermediate EPSG:4326 dataset.

One feature per placemark with valid line parts; multipart lines stay together.
Unique KML placemark IDs are preserved. Otherwise IDs use the KML member and
one-based source placemark index (stable for the same archive ordering).
Empty/invalid parts are reported individually. Valid lines are never clipped,
merged or removed for duplicates, boundary coverage or review flags.
Lengths are planar meters in EPSG:32639; optional KML altitude is omitted and
nonzero omissions reported. Source labels do not establish operation, safety,
completeness or connectivity. No MPV/MPS data is read.
"""

import argparse
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, mapping, shape
from shapely.validation import explain_validity


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data/raw/ayna/movcud-zolaqlar-velo(1).kmz"
BOUNDARY_PATH = PROJECT_ROOT / "data/processed/boundaries/baku_boundary.geojson"
OUTPUT_PATH = PROJECT_ROOT / "data/processed/transport/cycleways.geojson"
NS = {"k": "http://www.opengis.net/kml/2.2"}
LONG_SEGMENT_METERS = 1000.0
SHORT_LINE_METERS = 10.0


def read_kmz(path):
    records = []
    with ZipFile(path) as archive:
        print(f"KMZ members: {archive.namelist()}")
        members = [name for name in archive.namelist() if name.lower().endswith(".kml")]
        if not members or len(set(members)) != len(members):
            raise RuntimeError("Missing KML or duplicate archive member names.")
        for member in members:
            root = ET.fromstring(archive.read(member))
            if root.tag != f"{{{NS['k']}}}kml":
                raise RuntimeError(f"Unsupported KML root/namespace: {root.tag}")
            labels = [element.findtext("k:name", namespaces=NS)
                      for element in root.iter()
                      if element.tag in (f"{{{NS['k']}}}Document", f"{{{NS['k']}}}Folder")]
            print(f"Source document/folder names in {member}: {labels!r}")
            for index, placemark in enumerate(root.findall(".//k:Placemark", NS), 1):
                records.append({"member": member, "index": index,
                                "name": placemark.findtext("k:name", namespaces=NS),
                                "source_id": placemark.get("id"), "placemark": placemark})
    if not records:
        raise RuntimeError("No source placemarks found.")
    print(f"Source placemarks: {len(records)}; CRS: KML WGS84 longitude/latitude")
    print("Source placemark names: " + json.dumps([r["name"] for r in records], ensure_ascii=False))
    return records


def load_boundary():
    frame = gpd.read_file(BOUNDARY_PATH)
    if len(frame) != 1 or frame.crs is None:
        raise RuntimeError("Expected one study boundary with a declared CRS.")
    polygon = frame.to_crs("EPSG:4326").geometry.iloc[0]
    if (polygon is None or polygon.is_empty or not polygon.is_valid
            or polygon.geom_type not in {"Polygon", "MultiPolygon"}):
        raise RuntimeError("Study boundary must be a valid nonempty polygon.")
    return polygon


def parse_line(line):
    tokens = line.findtext("k:coordinates", default="", namespaces=NS).split()
    if not tokens:
        raise ValueError("empty: no coordinates")
    coordinates, nonzero_altitude = [], False
    for token in tokens:
        values = [float(value) for value in token.split(",")]
        if len(values) not in (2, 3) or not all(math.isfinite(v) for v in values):
            raise ValueError("invalid: expected finite longitude/latitude and optional altitude")
        lon, lat = values[:2]
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("invalid: coordinates outside longitude/latitude ranges")
        nonzero_altitude |= len(values) == 3 and values[2] != 0
        coordinates.append((lon, lat))
    if len(coordinates) < 2:
        raise ValueError("invalid: fewer than two vertices")
    geometry = LineString(coordinates)
    if not geometry.is_valid:
        raise ValueError(f"invalid: {explain_validity(geometry)}")
    return geometry, nonzero_altitude


def build_document(records, boundary):
    features, geometries = [], []
    exclusions = Counter()
    source_parts = retained_parts = excluded_placemarks = 0
    id_counts = Counter(r["source_id"] for r in records if r["source_id"])
    print(f"Repeated source IDs (index fallback): {dict((k, v) for k, v in id_counts.items() if v > 1)}")
    # Reserve every source ID so generated IDs cannot collide with one.
    reserved = set(id_counts)
    for record in records:
        identifier = record["source_id"]
        if not identifier or id_counts[identifier] != 1:
            identifier = f"ayna:cycleways:{record['member']}:placemark:{record['index']}"
            while identifier in reserved:
                identifier = "source-index:" + identifier
        parts, altitude = [], False
        for element in record["placemark"].iter():
            local = element.tag.rsplit("}", 1)[-1]
            if local in {"Point", "Polygon", "Model", "Track", "MultiTrack"}:
                raise RuntimeError(f"Unexpected {local} at {record['member']} placemark {record['index']}; inspect changed source structure.")
        lines = record["placemark"].findall(".//k:LineString", NS)
        source_parts += len(lines)
        for part_index, line in enumerate(lines, 1):
            try:
                geometry, omitted = parse_line(line)
                parts.append(geometry)
                altitude |= omitted
            except ValueError as exc:
                reason = str(exc)
                category = "empty" if reason.startswith("empty:") else "invalid"
                exclusions[category] += 1
                print("EXCLUDED PART: " + json.dumps({"member": record["member"],
                      "placemark_index": record["index"], "part_index": part_index,
                      "name": record["name"], "reason": reason}, ensure_ascii=False))
        if not parts:
            excluded_placemarks += 1
            print(f"EXCLUDED PLACEMARK: {identifier}; name={record['name']!r}; no valid line parts")
            continue
        geometry = parts[0] if len(parts) == 1 else MultiLineString(parts)
        if not geometry.is_valid or geometry.is_empty:
            raise RuntimeError(f"Assembled geometry invalid: {identifier}; refusing to drop valid parts.")
        retained_parts += len(parts)
        name = record["name"]
        if name is not None and not name.strip():
            name = None
        features.append({"type": "Feature", "id": identifier,
                         "properties": {"id": identifier, "name": name,
                                        "length_m": None, "source": "AYNA"},
                         "geometry": mapping(geometry)})
        geometries.append(geometry)
        if altitude:
            print(f"REVIEW: {identifier}; nonzero KML altitude omitted for 2D output")
    print(f"Source / retained / excluded placemarks: {len(records)} / {len(features)} / {excluded_placemarks}")
    print(f"Source / retained / excluded line parts: {source_parts} / {retained_parts} / {sum(exclusions.values())}")
    print(f"Empty / invalid part exclusions: {exclusions['empty']} / {exclusions['invalid']}")
    ids = [f["id"] for f in features]
    if (not features or len(set(ids)) != len(ids)
            or len(features) + excluded_placemarks != len(records)
            or retained_parts + sum(exclusions.values()) != source_parts):
        raise RuntimeError("No valid lines, duplicate output IDs or count reconciliation failed.")
    geographic = gpd.GeoSeries(geometries, crs="EPSG:4326")
    metric = geographic.to_crs("EPSG:32639")
    suspicious = 0
    for feature, original, projected in zip(features, geometries, metric, strict=True):
        length = float(projected.length)
        feature["properties"]["length_m"] = length if math.isfinite(length) else None
        parts = list(projected.geoms) if projected.geom_type == "MultiLineString" else [projected]
        segments = [math.hypot(b[0] - a[0], b[1] - a[1]) for part in parts
                    for a, b in zip(list(part.coords), list(part.coords)[1:])]
        flags = []
        if not math.isfinite(length):
            flags.append("unavailable_metric_length")
        elif length < SHORT_LINE_METERS:
            flags.append("length_under_10m")
        if max(segments) > LONG_SEGMENT_METERS:
            flags.append("vertex_segment_over_1000m")
        if not original.is_simple:
            flags.append("non_simple_or_self_intersecting")
        if any(segment == 0 for segment in segments):
            flags.append("repeated_adjacent_vertex")
        if flags:
            suspicious += 1
            print(f"REVIEW (retained): {feature['id']}; name={feature['properties']['name']!r}; "
                  f"length_m={length}; max_segment_m={max(segments)}; flags={flags}")
    exact_pairs, equal_pairs = [], []
    for i, geometry in enumerate(geometries):
        for j in range(i + 1, len(geometries)):
            if geometry.wkb == geometries[j].wkb:
                exact_pairs.append([ids[i], ids[j]])
            if geometry.equals(geometries[j]):
                equal_pairs.append([ids[i], ids[j]])
    names = Counter(f["properties"]["name"] for f in features)
    print(f"Output geometry types: {dict(Counter(g.geom_type for g in geometries))}; unique IDs: {len(set(ids))}")
    print(f"Missing names (JSON null): {names.get(None, 0)}")
    print(f"Repeated names (retained): {dict((k, v) for k, v in names.items() if v > 1)}")
    print(f"Exact WKB duplicate pairs (retained): {exact_pairs}")
    print(f"Topologically equal pairs, including reversed lines (retained): {equal_pairs}")
    print(f"Suspicious features (retained): {suspicious}; thresholds: length <10 m, vertex segment >1000 m")
    print(f"Boundary fully covered / partial / outside: {sum(boundary.covers(g) for g in geometries)} / "
          f"{sum(boundary.intersects(g) and not boundary.covers(g) for g in geometries)} / "
          f"{sum(not boundary.intersects(g) for g in geometries)}; no clipping")
    for feature, geometry in zip(features, geometries, strict=True):
        if not boundary.covers(geometry):
            print(f"BOUNDARY REVIEW (retained): {feature['id']}; name={feature['properties']['name']!r}")
    lengths = [f["properties"]["length_m"] for f in features]
    print(f"Total source-feature length: {math.fsum(v for v in lengths if v is not None) / 1000:.6f} km "
          f"(EPSG:32639; unavailable lengths={lengths.count(None)}; overlaps counted per feature)")
    print(f"Output CRS: EPSG:4326 longitude/latitude; bounds: {geographic.total_bounds.tolist()}")
    return json.loads(json.dumps({"type": "FeatureCollection", "features": features}, allow_nan=False))


def verify_saved(path, expected):
    with path.open(encoding="utf-8") as source:
        saved = json.load(source)
    if saved != expected:
        raise RuntimeError("Saved JSON differs from source-derived counts, IDs, names, geometries or lengths.")
    frame = gpd.read_file(path)
    if (len(frame) != len(expected["features"]) or frame.crs is None or frame.crs.to_epsg() != 4326
            or not frame.geom_type.isin(["LineString", "MultiLineString"]).all()
            or not frame.is_valid.all() or frame.is_empty.any()
            or frame["id"].tolist() != [f["id"] for f in expected["features"]]):
        raise RuntimeError("Reload failed count, ID, CRS or valid-line checks.")
    lengths = frame.to_crs("EPSG:32639").length
    for index, feature in enumerate(expected["features"]):
        if not frame.geometry.iloc[index].equals_exact(shape(feature["geometry"]), tolerance=0):
            raise RuntimeError(f"Reload geometry changed: {feature['id']}")
        length = feature["properties"]["length_m"]
        measured = float(lengths.iloc[index])
        if ((length is None and math.isfinite(measured)) or
                (length is not None and not math.isclose(length, measured, rel_tol=1e-12, abs_tol=1e-6))):
            raise RuntimeError(f"Reload metric length changed: {feature['id']}")
    print("Reload verification: PASSED (counts, unique string IDs, names, exact geometries, EPSG:4326 and EPSG:32639 lengths)")


def save_output(document):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=OUTPUT_PATH.parent,
                                prefix=".cycleways-", suffix=".geojson", delete=False) as output:
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
    print(f"Processed intermediate cycleways saved: {OUTPUT_PATH}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Rebuild expected data and validate saved output without writing.")
    args = parser.parse_args()
    document = build_document(read_kmz(RAW_PATH), load_boundary())
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
