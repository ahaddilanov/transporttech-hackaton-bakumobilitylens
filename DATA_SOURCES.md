# Data Sources

Local inspection date: 2026-10-10. This is an audit date, not an acquisition date.
See [DATA_INVENTORY.md](DATA_INVENTORY.md) for availability and outstanding gaps.
Evidence comes from existing files, scripts, embedded metadata, the earlier source
log and the original inventory draft in `~/Downloads`. No data was downloaded for
this documentation update. Filesystem timestamps are not treated as provenance.

## Baku administrative study boundary

- Source: geoBoundaries, Azerbaijan ADM2, selected `Baku City` feature.
- Source URL used by [01_download_boundary.py](scripts/01_download_boundary.py): https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/AZE/ADM2/geoBoundaries-AZE-ADM2.geojson
- Raw file: `data/raw/boundaries/geoboundaries_aze_adm2.geojson`.
- Validated study file: `data/processed/boundaries/baku_boundary.geojson`.
- Retrieval date: 2026-10-07, as recorded in the earlier source log; not embedded in the GeoJSON.
- License: the earlier source log records CC BY-SA 3.0. This inspection did not independently verify that statement; the local GeoJSON does not embed a license.
- Observed fields: `shapeISO`, `shapeName`, `shapeID`, `shapeGroup`, `shapeType`, geometry.
- Observed selection: `shapeID=54616110B61947743987915`, `shapeName=Baku City`, `shapeGroup=AZE`, `shapeType=ADM2`.
- Validation: one nonempty valid MultiPolygon; EPSG:4326; approximately 2,112.63 km² measured in EPSG:32639.
- Bounds `[west, south, east, north]`: `[49.303322328, 39.677316155, 50.620288976, 40.594470474]`.
- Use: fixed project study polygon for spatial scope and comparisons.
- Limitations: a research boundary, not a verified current legal/cadastral boundary. Its source vintage was not established from the local metadata; a year mentioned in an earlier draft is not independently confirmed here.

## Baku driving road network

- Source: OpenStreetMap; https://www.openstreetmap.org/.
- Method: OSMnx 2.1.1, `graph_from_polygon`, `network_type="drive"`, `simplify=True`, `retain_all=True`, using the study boundary; see [02_download_drive_network.py](scripts/02_download_drive_network.py).
- Local file: `data/processed/networks/baku_drive.graphml`.
- Observed graph: 78,876 nodes and 183,990 directed edges; CRS `epsg:4326`; `simplified=True`.
- Embedded graph metadata: `created_with=OSMnx 2.1.1`, `created_date=2026-10-07 22:22:30`; no timezone is recorded.
- Retrieval date: 2026-10-07 in the earlier source log. Graph creation time is not a separate proof of the precise source snapshot time.
- License/attribution: not embedded in the inspected graph; applicable OSM licensing and attribution need to be recorded before publication.
- Use: motor-vehicle routing and road context within the queried study region.
- Limitations: community mapping does not establish road completeness or current operational access. This is a driving graph, not a pedestrian network or evidence of bus service.

## Provisional OSM Baku bus stops

- Source: OpenStreetMap via Overpass; https://www.openstreetmap.org/.
- Method: OSMnx 2.1.1 `features_from_polygon(study_polygon, tags={"highway": "bus_stop"})`; see [03_audit_bus_stops.py](scripts/03_audit_bus_stops.py).
- Raw file: `data/raw/osm/baku_bus_stops_raw.geojson`.
- Observed result: 1,414 features, all Point geometries, EPSG:4326. There are 126 missing/blank `name` values, zero invalid geometries, zero duplicate OSM index pairs and zero exact duplicate geometries.
- Bounds `[west, south, east, north]`: `[49.4011599, 39.9472861, 50.3127868, 40.5880653]`.
- Preservation: all returned tag properties remain in the raw GeoJSON. Feature `id` identifies the OSM element; `osm_index.names=["element", "id"]` and `osm_index.values` preserve the original element type and numeric OSM ID separately from tags.
- Observed tags include `name`, localized names, `highway`, `public_transport`, `bus`, `ref`, `route_ref`, `operator`, `shelter`, `bench` and `wheelchair`. These are observed OSM fields, not an official AYNA schema or required contract fields.
- Acquisition date and exact source snapshot time: not recorded in the saved GeoJSON; do not infer them from file modification time. License/attribution is not embedded; applicable OSM terms remain to be documented.
- Geometry caveat: OSMnx may repair invalid geometries internally; this raw file preserves the geometries returned by OSMnx, not necessarily pre-repair API geometry.
- Use: provisional mapped-stop positions for exploratory spatial screening.
- Limitations: these stops are not officially AYNA-verified. The query is restricted to `highway=bus_stop`, and the count is not proof of exhaustive coverage, active service or a complete official stop inventory.
- Official AYNA stop-to-route relationships are unavailable for this project. Only 11 features have a non-null OSM `route_ref`; community tags and proximity to a route line do not establish official stop service, stop order or route membership.

## WorldPop Azerbaijan 2026 constrained population counts

- Source: WorldPop, Global 2015–2030, release R2025A, year 2026, v1, constrained approximately 100 m population-count product.
- Exact source URL: https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2026/AZE/v1/100m/constrained/aze_pop_2026_CN_100m_R2025A_v1.tif
- Untouched raw file: `data/raw/population/aze_pop_2026_CN_100m_R2025A_v1.tif`.
- Acquisition/validation method: [04_audit_population.py](scripts/04_audit_population.py) downloads to a temporary file, checks transfer length when provided, reads every raster block, validates metadata and values, then moves the validated bytes into place. Valid existing files are reused. `--verify-only` never downloads.
- Embedded document name: `aze_pop_2026_CN_100m_R2025A_v1`; description: `AZE population 2026 [WorldPop R2025A v1]`.
- Embedded license tag: `TIFFTAG_COPYRIGHT=CC-BY-4.0`.
- Embedded TIFF date: `2025-07-31 13:11:35`. This is file metadata, not the project acquisition date, census date or proof of a publication date. The modeled population year is 2026; acquisition date is not embedded in the file.
- Observed metadata: single-band GeoTIFF; EPSG:4326; resolution X/Y `0.00083333333` degrees; 7,391 columns × 4,223 rows; `float32`; NoData `-99999`; scale 1, offset 0.
- Bounds `[west, south, east, north]`: `[44.76416576761, 38.39250018243, 50.92333240964, 41.91166683502]`.
- File size: 9,735,419 bytes. SHA-256: `a4f171e60f6066efe356adf8a59884281bc3e44955e0c1e368f2d282d393a466`.
- Whole-country valid pixels: 1,685,745; masked pixels: 29,526,448. Valid-value minimum 0, maximum 231.527466, mean 6.185431, population standard deviation 12.088894; 2,994 valid zero-valued pixels; no unmasked negative/non-finite values observed.
- The raster footprint covers the full Baku study polygon. This does not mean all pixels within the polygon have valid values.

### Provisional Baku population interpretation

The project-reported sum **2,898,185** was reproduced in a read-only check as
2,898,185.146993 before rounding. Native-resolution pixels were selected by
whether their centers fall inside the study polygon (`all_touched=False`);
only finite, unmasked values contributed to the sum. No raster or derived
population dataset was written. This is a documentation check, not an output
of the existing whole-country audit script.

Of 322,482 pixel centers inside the polygon, 148,659 have valid values:
**46.1%** (46.0984% before rounding). The denominator is in-polygon pixels,
not the whole Azerbaijan raster, and this pixel-count percentage is not a
population coverage percentage. NoData is not automatically zero and must
remain distinct from observed zero-valued pixels. Do not extrapolate the sum
to the masked portion or silently fill it with zero.

The provisional total differs from the reported official benchmark and requires
careful interpretation. The benchmark's numeric value, source, reference date
and geographic definition were not established in the inspected project files;
no discrepancy percentage is asserted here. Before comparison or use as a
validated Baku population denominator, reconcile the benchmark's boundary,
population concept and year with the WorldPop model, verify the study-polygon
definition, and investigate the constrained product's NoData semantics. These
are checks to perform, not established explanations of the difference. The
raster is modeled population, not an official Baku census or predicted ridership.

## Four original AYNA transport resources

AYNA attribution comes from the project's description of the original supplied
files. The inspected files do not independently establish a provider URL,
license, acquisition date, publication date or complete/current operating status.
They are present under `~/Downloads`, not copied into this repository's
`data/raw/`. The existing inventory draft is supporting context, not proof of
fields or provenance that the originals do not contain.

| Original file and observed structure | Observed content | Intended use and limitations |
|---|---|---|
| `~/Downloads/buslines(1).kmz`; `doc.kml` plus XSL | 243 named placemarks, 239 distinct labels, 270 nonempty valid LineStrings. KML document/folder label `BusLinesAll271125`; descriptions inspected contain HTML `FID`, `Name`, `Shape_Leng`. Coordinates follow KML longitude/latitude convention. | Candidate bus-route geometry. One label can have multiple line parts; `Shape_Leng` units are not verified. The folder label is not a verified date. No official stop-to-route table, stop sequence, service frequency or active-service verification is supplied. |
| `~/Downloads/map(1).geojson`; FeatureCollection | 69 valid Point geometries. Observed properties: `name`, `description`, `styleUrl`, `fill-opacity`, `fill`, `stroke-opacity`, `label-opacity`, `label-color`, `icon`. HTML descriptions include `FID`, `Name`, `X`, `Y`; no explicit CRS member. Names identify regional/intercity terminals. | Terminal POI context; not an ordinary neighborhood bus-stop inventory. Geographic coordinate convention is observed, not a separately supplied CRS declaration. Completeness and operational status are unverified. |
| `~/Downloads/movcud-zolaqlar-velo.kmz`; `doc.kml` | 61 LineStrings: 60 nonempty valid lines and one empty line. Document/folder labels include `VELO YOL 2026` and `Mövcud zolaqlar`; named street segments, KML longitude/latitude convention. | Candidate bicycle-lane geometry. Labels suggest an existing-lanes grouping but do not verify the survey year or current operation. Directionality, surveyed completeness and license are unknown. |
| `~/Downloads/mpv-v-mps.-son(1).kmz`; `doc.kml` and icon files | 889 placemarks: 844 Points and 45 LineStrings, of which 44 are nonempty valid and one empty. Point labels include 649 `MPS-*` and 185 `MPV-*`; ten other points belong to example sightseeing content. Folder labels mention 2025; 230 `gx:TimeStamp` elements are present. | Candidate bicycle/micro-mobility points and supplemental linework. `MPS`/`MPV` meanings and planned versus active status are unresolved; timestamps are not assumed to be opening dates. Exclude unrelated tour points from Baku analysis. Do not concatenate overlapping lane files without comparison. |

Neither route-line proximity nor the 69 terminal POIs supplies the unavailable
official AYNA stop-to-route relationships. Original fields and geometry must
be preserved until a separately authorized processing step; this documentation
does not normalize files or change Shared Contract V1.

## Additional local supporting inputs

The earlier inventory draft recorded the following OpenData publisher references.
Their live availability and the provenance link between each page and each local
CSV were not rechecked in this local-only update. Licenses and acquisition dates
remain unconfirmed. These existing files are in `~/Downloads`, not integrated
into repository outputs.

- `bakubus_passenger-2026.csv`: 13,801 rows, 65 distinct route labels, observed dates 2026-01-01 through 2026-08-31. Actual headers: `Tarix (il-ay-gün)`, `Marşrutun adı`, `Gündəlik gediş sayı`. Prior publisher reference: https://opendata.az/en/%40baki-metropoliteni/bakubus-marsrutlari-uzre-gundelik-sernisin-gedislerinin-sayi-2026 . Route/day demand context only; not stop-level boardings or unique riders. Route matching remains unvalidated; not a complete-year file.
- `passenger-2026.csv`: 6,561 rows, 27 distinct station labels, observed dates 2026-01-01 through 2026-08-31. Actual headers: `Tarix (gün.ay.il)`, `Stansiya`, `Gündəlik gediş sayı`. Prior publisher reference: https://opendata.az/en/%40baki-metropoliteni/stansiyalar-uzre-gundelik-sernisin-gedislerinin-sayi . Station-entry context, not origin–destination trips or exits; not a complete-year file.
- `pathways.csv`: 98 rows. Actual headers: `Stansiya`, `Station`, `coğrafi enliyi (latitude)`, `coğrafi uzunluğu (longitude)`, `yerləşdiyi ünvan`, `Çıxış nörmələri`. Coordinates are integer-valued in the file (for example `40421499`, `49778066`); the earlier publisher description identifies microdegrees. Prior reference: https://opendata.az/en/%40baki-metropoliteni/metro-cixislari-uzre-koordinatlar . Conversion and spatial validation are still required before using these as metro-exit geometries.
