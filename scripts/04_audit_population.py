"""Download and audit the untouched WorldPop AZE 2026 R2025A count raster.

Only whole-raster pixel statistics and footprint overlap are calculated.
No raster transformation or derived dataset is written.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

try:
    import rasterio
except ModuleNotFoundError:
    sys.exit("Rasterio is required. Install project dependencies with: "
             ".venv/bin/python -m pip install -r requirements.txt")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2015_2030/"
    "R2025A/2026/AZE/v1/100m/constrained/aze_pop_2026_CN_100m_R2025A_v1.tif"
)
OUTPUT_PATH = PROJECT_ROOT / "data/raw/population/aze_pop_2026_CN_100m_R2025A_v1.tif"
BOUNDARY_PATH = PROJECT_ROOT / "data/processed/boundaries/baku_boundary.geojson"


def load_boundary():
    boundary = gpd.read_file(BOUNDARY_PATH)
    if boundary.empty or boundary.crs is None:
        raise RuntimeError("Baku boundary is empty or has no CRS.")
    geometries = boundary.geometry
    if (geometries.isna().any() or geometries.is_empty.any()
            or not geometries.is_valid.all()
            or not geometries.geom_type.isin(["Polygon", "MultiPolygon"]).all()):
        raise RuntimeError("Baku boundary contains missing, empty, invalid or non-polygon geometries.")
    return boundary


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pixel_statistics(dataset):
    count = zeros = negatives = nonfinite = 0
    mean = m2 = 0.0
    minimum, maximum = float("inf"), float("-inf")
    # Reading every native block also detects damaged/truncated pixel data.
    for _, window in dataset.block_windows(1):
        values = dataset.read(1, window=window, masked=True).compressed().astype("float64")
        finite = np.isfinite(values)
        nonfinite += int((~finite).sum())
        values = values[finite]
        size = values.size
        if not size:
            continue
        zeros += int((values == 0).sum())
        negatives += int((values < 0).sum())
        minimum = min(minimum, float(values.min()))
        maximum = max(maximum, float(values.max()))
        # Merge block moments rather than subtracting large squared sums.
        block_mean = float(values.mean())
        block_m2 = float(np.square(values - block_mean).sum())
        delta = block_mean - mean
        combined = count + size
        m2 += block_m2 + delta * delta * count * size / combined
        mean += delta * size / combined
        count = combined
    if nonfinite:
        raise RuntimeError(f"Raster contains {nonfinite} unmasked non-finite pixels.")
    if not count:
        raise RuntimeError("Raster contains no valid population pixels.")
    if negatives:
        raise RuntimeError(f"Raster contains {negatives} negative population values outside NoData.")
    return {
        "valid_pixel_count": int(count),
        "masked_pixel_count": int(dataset.width * dataset.height - count),
        "population_values": {
            "scope": "whole-country stored pixel values; NoData excluded",
            "minimum": minimum, "maximum": maximum, "mean": mean,
            "standard_deviation_population": float(np.sqrt(m2 / count)),
            "zero_pixel_count": zeros, "negative_pixel_count": negatives,
            "unmasked_nonfinite_pixel_count": nonfinite,
        },
    }


def inspect_raster(path, boundary):
    with rasterio.open(path, "r") as dataset:
        if dataset.driver != "GTiff" or dataset.count != 1:
            raise RuntimeError(f"Expected a single-band GeoTIFF; got {dataset.driver}, {dataset.count} bands.")
        if dataset.crs is None or dataset.width <= 0 or dataset.height <= 0:
            raise RuntimeError("Raster has no CRS or has empty dimensions.")
        if not np.isfinite(tuple(dataset.transform)).all() or dataset.transform.is_degenerate:
            raise RuntimeError("Raster affine transform is non-finite or degenerate.")
        if np.dtype(dataset.dtypes[0]).kind not in "iuf":
            raise RuntimeError(f"Unexpected population dtype: {dataset.dtypes[0]}")

        # Transform only the vector boundary, keeping all raster bytes intact.
        study = boundary.to_crs(dataset.crs).geometry.union_all()
        footprint = Polygon([dataset.transform * corner for corner in (
            (0, 0), (dataset.width, 0),
            (dataset.width, dataset.height), (0, dataset.height),
        )])
        intersection = footprint.intersection(study)
        # Extent overlap is not a claim about valid/populated pixel coverage.
        areas = gpd.GeoSeries([study, intersection], crs=dataset.crs).to_crs("EPSG:32639").area
        overlap = {
            "boundary_path": str(BOUNDARY_PATH),
            "scope": "geometric raster footprint, not valid-pixel coverage",
            "intersects": bool(footprint.intersects(study)),
            "covers_entire_boundary": bool(footprint.covers(study)),
            "intersection_bounds_in_raster_crs": list(intersection.bounds) if not intersection.is_empty else None,
            "intersection_area_km2": float(areas.iloc[1] / 1_000_000),
            "boundary_area_covered_percent": float(100 * areas.iloc[1] / areas.iloc[0]),
            "area_measurement_crs": "EPSG:32639",
        }
        if areas.iloc[1] <= 0:
            raise RuntimeError("Raster footprint has no positive-area overlap with Baku boundary.")
        nodata = dataset.nodata
        report = {
            "file": str(path), "source_url": SOURCE_URL,
            "file_size_bytes": path.stat().st_size,
            "file_size_MiB": path.stat().st_size / (1024 * 1024),
            "driver": dataset.driver, "crs": str(dataset.crs),
            "resolution_xy": list(dataset.res),
            "resolution_units": "degrees" if dataset.crs.is_geographic else dataset.crs.linear_units,
            "nominal_source_resolution": "approximately 100 m; actual resolution reported above",
            "width_columns": dataset.width, "height_rows": dataset.height,
            "band_count": dataset.count, "bounds_in_raster_crs": list(dataset.bounds),
            "dtype": dataset.dtypes[0],
            "NoData": repr(nodata) if nodata is not None and not np.isfinite(nodata) else nodata,
            "scale": dataset.scales[0], "offset": dataset.offsets[0],
            "block_shapes": dataset.block_shapes,
            "baku_overlap": overlap,
        }
        report.update(pixel_statistics(dataset))
    report["sha256"] = sha256(path)
    return report


def obtain_raster(boundary, verify_only=False):
    if OUTPUT_PATH.exists():
        print(f"Validating existing file: {OUTPUT_PATH}", flush=True)
        try:
            report = inspect_raster(OUTPUT_PATH, boundary)
        except (OSError, ValueError, RuntimeError, rasterio.errors.RasterioError) as exc:
            if verify_only:
                raise RuntimeError(f"Existing raster failed validation: {exc}") from exc
            print(f"Existing raster is invalid: {exc}. Downloading a replacement.", flush=True)
        else:
            print("Reusing validated existing raster; no download needed.")
            return report
    if verify_only:
        raise RuntimeError(f"No local raster to verify: {OUTPUT_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        request = Request(SOURCE_URL, headers={
            "User-Agent": "TransportTech-Population-Audit/0.1",
            "Accept-Encoding": "identity",
        })
        print(f"Downloading official WorldPop source: {SOURCE_URL}", flush=True)
        with urlopen(request, timeout=120) as response:
            if response.status != 200:
                raise RuntimeError(f"Expected HTTP 200, got {response.status}.")
            length = response.headers.get("Content-Length")
            expected_size = int(length) if length is not None else None
            received = 0
            with NamedTemporaryFile(dir=OUTPUT_PATH.parent, prefix=".worldpop-", suffix=".part", delete=False) as output:
                temporary_path = Path(output.name)
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    received += len(chunk)
                output.flush()
                os.fsync(output.fileno())
        if received == 0 or (expected_size is not None and received != expected_size):
            raise RuntimeError(f"Incomplete download: received {received} bytes; expected {expected_size}.")
        print(f"Downloaded {received} bytes. Validating all raster blocks before moving into place ...", flush=True)
        report = inspect_raster(temporary_path, boundary)
        os.replace(temporary_path, OUTPUT_PATH)
        report["file"] = str(OUTPUT_PATH)
        print(f"Validated untouched GeoTIFF saved: {OUTPUT_PATH}")
        return report
    except Exception as exc:
        raise RuntimeError(
            f"WorldPop download/validation failed; final raster was not replaced. "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Audit the existing local raster; never download.")
    args = parser.parse_args()
    report = obtain_raster(load_boundary(), verify_only=args.verify_only)
    print(json.dumps(report, indent=2, allow_nan=False))
    print("Validation: PASSED (all pixel blocks read; raw raster unchanged)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
