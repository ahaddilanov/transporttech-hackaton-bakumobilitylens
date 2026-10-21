from pathlib import Path
from shutil import copyfileobj
from urllib.request import Request, urlopen

import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "boundaries"
    / "geoboundaries_aze_adm2.geojson"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "boundaries"
    / "baku_boundary.geojson"
)

SOURCE_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/"
    "9469f09/releaseData/gbOpen/AZE/ADM2/"
    "geoBoundaries-AZE-ADM2.geojson"
)

BAKU_SHAPE_ID = "54616110B61947743987915"
EXPECTED_NAME = "Baku City"


def download_dataset() -> None:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Downloading Azerbaijan ADM2 boundary dataset...")
    print(f"Source: {SOURCE_URL}")

    request = Request(
        SOURCE_URL,
        headers={
            "User-Agent": "TransportTech-Baku-Hackathon/0.1"
        },
    )

    with urlopen(request, timeout=120) as response:
        with RAW_PATH.open("wb") as output_file:
            copyfileobj(response, output_file)

    print(f"Saved raw dataset to: {RAW_PATH}")


def extract_baku_boundary() -> None:
    print()
    print("Loading boundary dataset...")

    gdf = gpd.read_file(RAW_PATH)

    if gdf.empty:
        raise RuntimeError("Boundary dataset is empty.")

    required_columns = {
        "shapeID",
        "shapeName",
        "shapeGroup",
        "shapeType",
        "geometry",
    }

    missing_columns = required_columns - set(gdf.columns)

    if missing_columns:
        raise RuntimeError(
            f"Missing expected columns: {sorted(missing_columns)}"
        )

    boundary = gdf.loc[
        gdf["shapeID"] == BAKU_SHAPE_ID
    ].copy()

    if len(boundary) != 1:
        raise RuntimeError(
            f"Expected exactly one Baku feature, got {len(boundary)}."
        )

    row = boundary.iloc[0]

    if row["shapeName"] != EXPECTED_NAME:
        raise RuntimeError(
            f"Unexpected feature name: {row['shapeName']}"
        )

    if boundary.crs is None:
        raise RuntimeError("Boundary has no CRS.")

    boundary = boundary.to_crs("EPSG:4326")

    geometry = boundary.geometry.iloc[0]

    if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise RuntimeError(
            f"Unexpected geometry type: {geometry.geom_type}"
        )

    if not geometry.is_valid:
        raise RuntimeError("Baku boundary geometry is invalid.")

    # Calculate area using a metric CRS suitable for Baku.
    boundary_metric = boundary.to_crs("EPSG:32639")
    area_km2 = boundary_metric.geometry.area.iloc[0] / 1_000_000

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    boundary.to_file(
        OUTPUT_PATH,
        driver="GeoJSON",
        index=False,
    )

    print()
    print("Baku boundary extracted successfully.")
    print(f"Name:       {row['shapeName']}")
    print(f"Shape ID:   {row['shapeID']}")
    print(f"Shape type: {row['shapeType']}")
    print(f"Geometry:   {geometry.geom_type}")
    print(f"CRS:        {boundary.crs}")
    print(f"Valid:      {geometry.is_valid}")
    print(f"Area:       {area_km2:.2f} km²")
    print(f"Bounds:     {boundary.total_bounds.tolist()}")
    print(f"Saved to:   {OUTPUT_PATH}")


def main() -> None:
    download_dataset()
    extract_baku_boundary()


if __name__ == "__main__":
    main()