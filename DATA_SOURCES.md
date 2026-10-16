# Data Sources

Local inspection date: 2026-10-10. This is an audit date, not an acquisition date.
See [DATA_INVENTORY.md](DATA_INVENTORY.md) for availability and outstanding gaps.
Evidence comes from existing files, scripts, embedded metadata, the earlier source
log and the original inventory draft in `~/Downloads`. No data was downloaded for
the original 2026-10-10 documentation update. Later retrievals are documented in
their own sections below. Filesystem timestamps are not treated as provenance.

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

## OSM bicycle-permissible study routing network — Step 16B-1

- Builder: [15_build_bike_network.py](scripts/15_build_bike_network.py), method
  `baku-bike-study-network-v1.0`; installed OSMnx **2.1.1** inspected before implementation.
- Source: [OpenStreetMap](https://www.openstreetmap.org/) via the configured Overpass
  endpoint `https://overpass-api.de/api`. Attribution: **© OpenStreetMap contributors**;
  database license: [Open Database License (ODbL) 1.0](https://www.openstreetmap.org/copyright).
- OSM retrieval date: **2026-10-16**; first complete remote acquisition finished
  at approximately **16:00 UTC**, with Overpass OSM base timestamp
  **`2026-10-16T15:58:48Z`**. The remote acquisition took **110.703 seconds**,
  including OSMnx's service-status wait. Final artifact construction reused that
  complete cached response after a metadata-serialization fix; no replacement
  query or smaller study area was substituted. Output metadata records the
  validated build's acquisition start/completion in UTC, OSM base timestamps,
  cached/fresh response counts and elapsed time. A cache-backed build timestamp
  is not a fresh remote retrieval or the precise source-edit time.
- Inputs: all **60** valid AYNA LineStrings in
  `data/processed/transport/cycleways.geojson`, with observed fields `id`, `name`,
  `length_m`, `source=AYNA`; and the actual `Baku City` MultiPolygon in
  `data/processed/boundaries/baku_boundary.geojson`. Both are EPSG:4326.
- Study definition: project both inputs to **EPSG:32639**, buffer every full line
  by **3,000 m** (16 segments per quarter circle), dissolve overlapping buffers,
  then intersect with the full Baku boundary, preserving polygon parts and holes.
  The inspected study area is **110.244005715 km²**, a valid single Polygon.
  Disconnected polygons are supported and never reduced to the largest part.
  The area is the exact geometric intersection; validation tolerates at most
  0.000001 m² of numerical overlay roundoff without changing the geometry.
- Query: reproject the study polygon to **EPSG:4326**, then call
  `graph_from_polygon(..., network_type="bike", simplify=False, retain_all=True,
  truncate_by_edge=False)`. These parameters follow the
  [OSMnx 2.1.1 graph API](https://osmnx.readthedocs.io/en/stable/user-reference.html#osmnx.graph.graph_from_polygon).
  OSMnx downloads with its internal 500 m perimeter buffer, then truncates to
  study-polygon nodes. Query-envelope and request-count preflight runs locally.
  The measured buffered convex query envelope is **171.549 km²** and requires
  **one** response, below OSMnx's default 2,500 km² subdivision threshold.
- Outputs: `data/processed/networks/baku_bike_study_area.geojson` is a one-feature
  EPSG:4326 Polygon/MultiPolygon FeatureCollection; `baku_bike.graphml` is a directed
  MultiDiGraph in **EPSG:32639**. Geographic node `lon`/`lat` are retained alongside
  metric `x`/`y`. Reusable OSMnx GraphML preserves OSM node IDs and edge topology.
  Existing driving-network files, processed inputs, scores and Shared Contract V1
  are not modified; no recommended cycling corridors are produced.
- Attribute preservation: configure useful OSM way/node tags before acquisition,
  including `highway`, `bicycle`, `cycleway`, directional/conditional variants,
  `access`, `oneway`, `bridge`, `tunnel`, `surface`, `smoothness`, `incline`, `lit`,
  `width`, `junction`, `service`, `maxspeed`, crossing and barrier tags where present.
  Each edge additionally retains **all original way tags** in `osm_tags_json`,
  including the original string `oneway`. OSMnx's normalized boolean `oneway`
  remains available for routing. Missing tags are not assigned invented values.
  No topological simplification, component pruning or ring removal is applied.
- Lengths: `length` preserves OSMnx's great-circle distance between adjacent OSM
  nodes in meters. `length_utm_m` is the corresponding EPSG:32639 segment-geometry
  length, also in meters. All geometric validation and study measurements are
  metric. Zero, negative, missing or nonfinite lengths fail; source/metric lengths
  must agree within 1% or 0.02 m for very short segments. Directed edges count
  each travel direction separately, so their counts/lengths are not unique roads.
- Validation: reject malformed/remarked Overpass responses, missing referenced
  nodes, conflicting duplicated source objects or incomplete response sets.
  Validate every node's geographic/metric coordinates and study inclusion; every
  edge's endpoints, geometry, finite positive lengths, normalized direction and
  raw-tag preservation; and reverse edges for non-oneway segments. Report all
  weak component sizes, strong-component size frequencies, isolated nodes,
  highway types, tag coverage and routing warnings. Validate GraphML roundtrip
  topology and every attribute before publication. The study GeoJSON records the
  GraphML SHA-256; mismatched or interrupted output pairs fail verification.
- Offline verification: recompute only the study definition from unchanged local
  inputs, load both outputs and check geometry, input/output hashes, acquisition
  provenance and graph quality. It does not query OSM or overwrite files.
  Existing complete outputs are validated/reused on ordinary reruns.
- Service-limit fallback: if the buffered query envelope exceeds 2,500 km² or
  requires more than 16 Overpass responses, stop before acquisition and report
  reproducible subdivision: a **5,000 m EPSG:32639 lattice anchored at (0,0)**,
  intersected with the entire study polygon, each nonempty tile queried with
  **500 m overlap**. Audit every tile, merge raw OSM nodes/ways by source IDs,
  reconcile duplicate objects, and only publish after every tile succeeds.
  This fallback is proposed explicitly, not silently executed. Timeouts and
  service errors never result in a partial graph labeled as complete.

Observed full-graph quality summary (directed edge counts, not unique roads):

| Check | Result |
| --- | ---: |
| Nodes / directed edges | 80,957 / 155,944 |
| GraphML file size | 107,144,495 bytes (about 102.18 MiB) |
| Final acquisition/build input phase using cached response | 7.422 seconds; 1 cached, 0 fresh responses |
| Weakly connected components | 103 |
| Five largest weak component node counts | 79,628; 553; 96; 60; 50 |
| Remaining 98 weak components | 570 nodes in total |
| Strongly connected components / largest node count | 793 / 78,582 |
| Isolated nodes retained after study clipping | 17 |
| Directed one-way edges | 18,334 |
| Edges with bicycle/conditional exception tags requiring review | 275 |
| Invalid coordinates, edge geometries or nonpositive lengths | 0 |
| Edges extending outside the study polygon | 0 |
| `highway=cycleway` / `path` / `track` directed edges | 3,892 / 1,978 / 1,480 |
| `service` / `living_street` / `residential` directed edges | 84,365 / 29,734 / 14,146 |

The complete weak-component size list, strong-component size histogram, all
highway types and available-tag counts are printed and stored in the study
GeoJSON. Isolated nodes and small components remain available for inspection;
they do not imply routable links to the main network. The graph also includes
OSM-filtered primary, trunk and busway segments: filter inclusion does not verify
legal access, traffic safety or protected cycling provision on those roads.

**Routing limitations:** bicycle-permissible OSM roads are **not verified safe
bicycle lanes**. OSM access/condition mapping can be missing or stale, and AYNA
line labels do not verify operating status or connection to OSM roads. The
OSMnx 2.1.1 `bike` filter excludes footways, including potentially legal cycling
links, and filters private/explicitly bicycle-prohibited ways. Its directed
graph uses general oneway/roundabout rules rather than fully interpreting
`oneway:bicycle`, contraflow or conditional access. Original exception tags are
preserved and counted for later assessment; no universal bidirectional assumption
is introduced. Turn-restriction relations, schedules, barrier passability, grades,
crossing safety and traffic stress are not modeled. Study-boundary truncation
can create artificial disconnections; routes leaving the study area are unavailable.
No disconnected component is silently dropped or bridged. Field/access/safety
assessment and bicycle-specific routing rules are required before corridor design.

Execution and offline verification from the repository root:

```bash
.venv/bin/python scripts/15_build_bike_network.py
.venv/bin/python scripts/15_build_bike_network.py --verify-only
.venv/bin/python -m unittest discover -s tests -v
```
