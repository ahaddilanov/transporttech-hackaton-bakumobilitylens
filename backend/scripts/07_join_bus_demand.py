"""Join documented BakuBus validation counts to exact normalized route refs.

Publisher evidence audited 2026-10-11: the resource description explicitly
identifies electronic-payment validations. Therefore avg_daily_validations is
appropriate; these are not unique riders, stop-level demand or complete trips.
The checked source URL and limitations are preserved in output metadata.

Normalization only trims outer whitespace and uppercases labels. Leading zeros,
internal whitespace and suffixes stay meaningful. Duplicate route-date pairs
abort, even if counts agree. Missing counts/dates never become zero; means use
unique dates with numeric observations. Totals count each route/date once,
regardless of how many geometry features share that route reference.
"""

import argparse
import copy
import csv
import hashlib
import io
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tempfile import NamedTemporaryFile

import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = PROJECT_ROOT / "data/processed/transport/bus_routes.geojson"
CSV_PATH = PROJECT_ROOT / "data/raw/opendata/bakubus_passenger-2026.csv"
OUTPUT_PATH = PROJECT_ROOT / "data/processed/transport/bus_routes_with_demand.geojson"
DATE_COLUMN = "Tarix (il-ay-gün)"
ROUTE_COLUMN = "Marşrutun adı"
COUNT_COLUMN = "Gündəlik gediş sayı"
SOURCE_URL = (
    "https://opendata.az/en/@baki-metropoliteni/"
    "bakubus-marsrutlari-uzre-gundelik-sernisin-gedislerinin-sayi-2026/"
    "r/bbed6c16-79dc-4b3d-a0b6-b0411dcda473"
)
SOURCE_EVIDENCE = {
    "resource_url": SOURCE_URL,
    "evidence_checked_date": "2026-10-11",
    "count_column": COUNT_COLUMN,
    "metric": "electronic_payment_validations",
    "description_basis": "Publisher identifies payment-equipment validation events, including Baki Kart and contactless payments.",
    "provider_as_documented": "K Group LLC (Baku Kart)",
    "limitations": ["not unique passengers", "not stop-level boarding/alighting or trip chains",
                    "technical/data-processing issues may affect accuracy",
                    "label agreement is not independent verification of current route identity"],
    "normalization": "strip outer whitespace, uppercase; preserve leading zeros, internal whitespace and suffixes",
    "mean_denominator": "unique observed dates with a numeric count; missing days/counts not zero",
    "totals_scope": "sum unique route-date observations, not geometry features or complete-calendar estimates",
}


def normalize_ref(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("route labels must be strings; no numeric coercion")
    return value.strip().upper() or None


def audit_csv(path):
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    text = raw.decode(encoding, errors="strict")
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=",")
    columns = reader.fieldnames
    if columns != [DATE_COLUMN, ROUTE_COLUMN, COUNT_COLUMN]:
        raise RuntimeError(f"CSV schema changed; actual columns: {columns}")
    rows = list(reader)
    if not rows:
        raise RuntimeError("CSV has no observations.")
    missing = Counter({column: 0 for column in columns})
    errors, pairs = [], defaultdict(list)
    labels, observations = defaultdict(set), defaultdict(dict)
    dates, numeric_counts = set(), []
    route_dates = defaultdict(set)
    for row_number, row in enumerate(rows, start=2):
        if None in row or any(row[column] is None for column in columns):
            errors.append({"CSV_row": row_number, "reason": "wrong number of CSV fields"})
            continue
        for column in columns:
            missing[column] += int(not row[column].strip())
        try:
            key = normalize_ref(row[ROUTE_COLUMN])
            if key is None:
                raise ValueError("missing route label")
            raw_date = row[DATE_COLUMN].strip()
            day = date.fromisoformat(raw_date)
            if day.isoformat() != raw_date or day.year != 2026:
                raise ValueError("expected ISO YYYY-MM-DD date in 2026")
            raw_count = row[COUNT_COLUMN].strip()
            count = None
            if raw_count:
                value = Decimal(raw_count)
                if not value.is_finite() or value < 0 or value != value.to_integral_value():
                    raise ValueError("count is not a finite nonnegative integer")
                count = int(value)
            pairs[(key, day)].append(row_number)
            labels[key].add(row[ROUTE_COLUMN])
            route_dates[key].add(day)
            dates.add(day)
            if count is not None:
                # Duplicates are detected and rejected below, never summed.
                observations[key][day] = count
                numeric_counts.append(count)
        except (ValueError, InvalidOperation) as exc:
            errors.append({"CSV_row": row_number, "reason": str(exc)})
    duplicates = [{"normalized_route_ref": key, "date": day.isoformat(), "CSV_rows": row_numbers}
                  for (key, day), row_numbers in sorted(pairs.items()) if len(row_numbers) > 1]
    print(f"CSV encoding: {encoding} (strict decode); bytes: {len(raw)}; CRLF lines: {raw.count(bytes([13, 10]))}")
    print(f"CSV columns: {columns}; rows: {len(rows)}")
    print(f"Missing values by column: {dict(missing)}")
    print(f"Invalid rows: {len(errors)}; duplicate normalized route-date combinations: {len(duplicates)}")
    for problem in errors + duplicates:
        print("CSV ERROR: " + json.dumps(problem, ensure_ascii=False))
    if errors or duplicates:
        raise RuntimeError("CSV audit failed; no output written/replaced. Resolve invalid or duplicate observations explicitly.")
    if not numeric_counts:
        raise RuntimeError("CSV has no numeric observations.")

    first, last = min(dates), max(dates)
    global_span = (last - first).days + 1
    stats = {}
    for key in sorted(labels):
        observed = observations[key]
        observed_days = sorted(observed)
        row_days = sorted(route_dates[key])
        span = (row_days[-1] - row_days[0]).days + 1
        total = sum(observed.values())
        stats[key] = {
            "csv_labels": sorted(labels[key]), "observation_days": len(observed),
            "first_observation_date": observed_days[0].isoformat() if observed_days else None,
            "last_observation_date": observed_days[-1].isoformat() if observed_days else None,
            "csv_row_days": len(row_days), "missing_numeric_count_days": len(row_days) - len(observed),
            "calendar_span_between_first_last_csv_dates": span,
            "days_without_numeric_observation_in_route_span": span - len(observed),
            "days_without_numeric_observation_in_global_span": global_span - len(observed),
            "observed_count_sum": total if observed else None,
            "mean_daily_count": total / len(observed) if observed else None,
        }
    audit = {
        "encoding": encoding, "columns": columns, "row_count": len(rows),
        "sha256": hashlib.sha256(raw).hexdigest(), "missing_values": dict(missing),
        "invalid_row_count": len(errors), "duplicate_route_date_count": len(duplicates),
        "date_min": first.isoformat(), "date_max": last.isoformat(),
        "distinct_csv_dates": len(dates), "calendar_span_days": global_span,
        "route_count": len(stats), "numeric_observation_count": len(numeric_counts),
        "count_min": min(numeric_counts), "count_max": max(numeric_counts),
        "zero_observation_count": numeric_counts.count(0),
        "total_observed_validations_unique_route_dates": sum(numeric_counts),
        "normalization_aliases": {key: sorted(values) for key, values in labels.items() if len(values) > 1},
    }
    if sum(value["observation_days"] for value in stats.values()) != len(numeric_counts):
        raise RuntimeError("CSV observation count reconciliation failed.")
    print("CSV AUDIT: " + json.dumps(audit, ensure_ascii=False))
    print("ROUTE OBSERVATION COVERAGE (absent days are not inferred to be zero or inactive):")
    for key, value in stats.items():
        print(f"  {key}: labels={value['csv_labels']!r}; observed_days={value['observation_days']}; "
              f"dates={value['first_observation_date']}..{value['last_observation_date']}; "
              f"unobserved_days_in_route_span={value['days_without_numeric_observation_in_route_span']}; "
              f"missing_count_days={value['missing_numeric_count_days']}; mean={value['mean_daily_count']}")
    return stats, audit


def load_routes(path):
    with path.open(encoding="utf-8") as source:
        document = json.load(source)
    if document.get("type") != "FeatureCollection" or len(document.get("features", [])) != 243:
        raise RuntimeError("Expected the previously validated 243 geometry features.")
    frame = gpd.read_file(path)
    if (frame.crs is None or frame.crs.to_epsg() != 4326
            or not frame.geom_type.isin(["LineString", "MultiLineString"]).all()
            or not frame.is_valid.all() or frame.is_empty.any()):
        raise RuntimeError("Input routes failed EPSG:4326/line geometry validation.")
    identifiers = []
    for feature in document["features"]:
        properties = feature["properties"]
        identifier = properties.get("id")
        if not isinstance(identifier, str) or not identifier or feature.get("id") != identifier:
            raise RuntimeError("Input route ID is missing, non-string or inconsistent.")
        normalize_ref(properties.get("route_ref"))
        if "avg_daily_validations" not in properties or properties["avg_daily_validations"] is not None:
            raise RuntimeError("Expected the unjoined input with avg_daily_validations=null.")
        identifiers.append(identifier)
    if len(set(identifiers)) != len(identifiers):
        raise RuntimeError("Input geometry IDs are not unique.")
    return document


def join_demand(original, stats, audit):
    document = copy.deepcopy(original)
    geometry_labels = defaultdict(set)
    geometry_counts = Counter()
    matched_features = 0
    for feature in document["features"]:
        properties = feature["properties"]
        key = normalize_ref(properties.get("route_ref"))
        if key is not None:
            geometry_labels[key].add(properties["route_ref"])
            geometry_counts[key] += 1
        demand = stats.get(key)
        matched_features += int(demand is not None)
        properties.update({
            "avg_daily_validations": demand["mean_daily_count"] if demand else None,
            "demand_normalized_route_ref": key,
            "demand_csv_labels": demand["csv_labels"] if demand else None,
            "demand_observation_days": demand["observation_days"] if demand else None,
            "demand_first_observation_date": demand["first_observation_date"] if demand else None,
            "demand_last_observation_date": demand["last_observation_date"] if demand else None,
            "demand_join_status": ("matched" if demand["observation_days"] else "matched_without_numeric_observations")
                                  if demand else "unmatched",
        })
    matched = set(geometry_labels) & set(stats)
    summary = {
        "geometry_features_before": len(original["features"]),
        "geometry_features_after": len(document["features"]),
        "matched_features": matched_features,
        "unmatched_features": len(document["features"]) - matched_features,
        "matched_unique_normalized_routes": len(matched),
        "missing_geometry_route_ref_count": sum(normalize_ref(f["properties"].get("route_ref")) is None for f in original["features"]),
        "unmatched_csv_labels": sorted(label for key in set(stats) - set(geometry_labels) for label in stats[key]["csv_labels"]),
        "unmatched_geometry_labels": sorted(label for key in set(geometry_labels) - set(stats) for label in geometry_labels[key]),
        "repeated_geometry_route_refs": {key: count for key, count in sorted(geometry_counts.items()) if count > 1},
        "geometry_normalization_aliases": {key: sorted(labels) for key, labels in geometry_labels.items() if len(labels) > 1},
        # Aggregate the route dictionary, never feature-attached demand values.
        "matched_numeric_route_date_observations": sum(stats[key]["observation_days"] for key in matched),
        "matched_total_observed_validations_unique_routes": sum(stats[key]["observed_count_sum"] or 0 for key in matched),
    }
    # These are count totals over recorded observations, not estimates for a
    # full calendar or a comparable-window sum of route means.
    document["demand_metadata"] = {
        "source_evidence": SOURCE_EVIDENCE, "csv_audit": audit,
        "route_observation_statistics": stats, "join_summary": summary,
    }
    if summary["matched_features"] + summary["unmatched_features"] != len(original["features"]):
        raise RuntimeError("Join feature count reconciliation failed.")
    print("SEMANTICS: avg_daily_validations is supported by the checked publisher description.")
    print("SOURCE EVIDENCE: " + json.dumps(SOURCE_EVIDENCE, ensure_ascii=False))
    print("JOIN SUMMARY: " + json.dumps(summary, ensure_ascii=False))
    return document


def verify_preservation(original, joined):
    additions = {"demand_normalized_route_ref", "demand_csv_labels", "demand_observation_days",
                 "demand_first_observation_date", "demand_last_observation_date", "demand_join_status"}
    if len(original["features"]) != len(joined["features"]):
        raise RuntimeError("Geometry feature count changed.")
    for before, after in zip(original["features"], joined["features"], strict=True):
        restored = copy.deepcopy(after)
        for key in additions:
            restored["properties"].pop(key)
        restored["properties"]["avg_daily_validations"] = None
        if restored != before:
            raise RuntimeError(f"Original feature/labels/IDs/geometry changed: {before.get('id')}")


def verify_saved(path, expected, original):
    with path.open(encoding="utf-8") as source:
        saved = json.load(source)
    if saved != expected:
        raise RuntimeError("Saved JSON differs from recomputed CSV means, join or metadata.")
    verify_preservation(original, saved)
    frame = gpd.read_file(path)
    if (len(frame) != 243 or frame.crs is None or frame.crs.to_epsg() != 4326
            or not frame.is_valid.all() or frame.is_empty.any()
            or not frame.geom_type.isin(["LineString", "MultiLineString"]).all()):
        raise RuntimeError("Reloaded geometry/count/CRS validation failed.")
    print("Reload/reconciliation: PASSED (243 features, IDs, original labels, exact geometries, observed-date means and metadata)")


def save_output(document, original):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=OUTPUT_PATH.parent,
                                prefix=".bus-demand-", suffix=".geojson", delete=False) as output:
            temporary = Path(output.name)
            json.dump(document, output, ensure_ascii=False, allow_nan=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        verify_saved(temporary, document, original)
        os.replace(temporary, OUTPUT_PATH)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f"Processed routes with demand saved: {OUTPUT_PATH}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Reaudit inputs and reconcile existing output without writing.")
    args = parser.parse_args()
    stats, audit = audit_csv(CSV_PATH)
    original = load_routes(ROUTES_PATH)
    document = join_demand(original, stats, audit)
    verify_preservation(original, document)
    if args.verify_only:
        verify_saved(OUTPUT_PATH, document, original)
    else:
        save_output(document, original)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
