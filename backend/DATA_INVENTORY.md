# TransportTech Data Inventory

> Historical source inspection below: 2026-10-10. For current processed-artifact
> availability, see the 2026-10-21 release addendum at the end of this document.
> Earlier statements such as “not integrated” are observations of that earlier
> inspection, not the status of today's completed pipeline.

Local inspection date: 2026-10-10. Study area: geoBoundaries AZE ADM2 `Baku City`,
`shapeID=54616110B61947743987915`. Provenance and detailed observations are in
[DATA_SOURCES.md](DATA_SOURCES.md). Audit dates, modeled years, embedded timestamps
and acquisition dates are distinct; unknown values remain unknown.

## Status definitions

| Status | Meaning |
|---|---|
| HAVE | File is actually present and was inspected; does not imply official verification, completeness, readiness for export or integration into this repository. |
| AVAILABLE | A specific external dataset is confirmed obtainable but has not been acquired; publisher descriptions are not an inspected file schema. |
| NEEDED | Required data or metadata remains unresolved or unavailable for this project. |
| OPTIONAL | Potentially useful input or enhancement; availability and fitness must be checked before adoption. |
| REJECTED | Excluded for a specified use, not necessarily discarded as a source file. |

## HAVE — acquired files

| Dataset | Actual location | Observed content | Current fitness and limitations |
|---|---|---|---|
| Validated Baku boundary | `data/processed/boundaries/baku_boundary.geojson`; raw AZE ADM2 in `data/raw/boundaries/geoboundaries_aze_adm2.geojson` | One valid MultiPolygon; EPSG:4326; approximately 2,112.63 km². | Fixed study polygon. Research boundary, not a verified current official legal boundary; source vintage unconfirmed. |
| OSM Baku driving network | `data/processed/networks/baku_drive.graphml` | 78,876 nodes, 183,990 directed edges; EPSG:4326; simplified drive graph, `retain_all=True`. | Motor-vehicle context; not a walking network or proof of bus operation. |
| OSM Baku mapped bus stops | `data/raw/osm/baku_bus_stops_raw.geojson` | **1,414 Point features**, EPSG:4326; all returned tags and OSM IDs preserved; 126 missing/blank names. | **Provisional and not officially AYNA-verified.** No completeness or active-service claim; not an official stop-to-route inventory. |
| WorldPop Azerbaijan 2026 R2025A v1 constrained counts, nominal ~100 m | `data/raw/population/aze_pop_2026_CN_100m_R2025A_v1.tif` | Untouched single-band float32 GeoTIFF; EPSG:4326; 0.00083333333° X/Y; 7,391 × 4,223; NoData −99999; embedded CC-BY-4.0. | Country-wide modeled population counts. Full Baku footprint overlap does not mean full valid-data coverage; Baku total remains provisional. |
| Original AYNA bus-route lines, per project attribution | `~/Downloads/buslines(1).kmz` | 243 placemarks, 239 distinct labels, 270 valid nonempty LineStrings; route labels and HTML attributes. | Candidate routes; no official stop sequence/linkages or verified operating date. Not yet copied or normalized into project data. |
| Original AYNA terminal points, per project attribution | `~/Downloads/map(1).geojson` | 69 valid Points; names, HTML descriptions and styling; regional/intercity terminals. | Terminal context only; **not ordinary local bus stops**. Not yet copied or normalized. |
| Original AYNA bicycle-lane linework, per project attribution | `~/Downloads/movcud-zolaqlar-velo.kmz` | 61 lines: 60 nonempty valid and one empty; folder labels mention 2026 and existing lanes. | Candidate cycleways; labels do not establish active status or survey date. Not yet copied or normalized. |
| Original AYNA bicycle points and supplemental linework, per project attribution | `~/Downloads/mpv-v-mps.-son(1).kmz` | 844 Points: 649 `MPS-*`, 185 `MPV-*`, ten unrelated tour points; 45 lines, 44 nonempty valid; 230 KML extension timestamps. | Class meanings and active/planned status unknown; inspect overlap with other lane file before combining. Not yet copied or normalized. |
| Local BakuBus route/day count CSV | `~/Downloads/bakubus_passenger-2026.csv` | 13,801 rows; 65 route labels; observed 2026-01-01 to 2026-08-31. | Route-level demand context only. Source-page provenance and joins to original route labels remain unverified; not a complete-year file. |
| Local metro station/day entry CSV | `~/Downloads/passenger-2026.csv` | 6,561 rows; 27 station labels; observed 2026-01-01 to 2026-08-31. | Entries are not OD trips, exits or unique riders. Not integrated; not a complete-year file. |
| Local metro-exit coordinate CSV | `~/Downloads/pathways.csv` | 98 rows; station names, integer-valued coordinate columns, address and exit label. | Candidate first/last-mile anchors; validate the reported microdegree conversion and geometry before use. |

The four original AYNA files are attributed by the project/user, not independently
authenticated through embedded provider metadata. Their licenses, acquisition
dates, publication dates and completeness remain unknown. Copies with other
filename suffixes also exist in Downloads; no equivalence, replacement order or
preferred version is inferred from filenames. Raw originals have not been moved,
modified or deduplicated by this documentation update.

## AVAILABLE — confirmed unacquired datasets

No additional unacquired dataset was newly confirmed as AVAILABLE in this
local-only inspection. The earlier draft's three OpenData references now have
related local CSVs listed under HAVE; that does not independently prove their
publisher provenance. Source links and this limitation are retained in
DATA_SOURCES.md. Other possible datasets stay OPTIONAL or NEEDED until verified;
an attractive publisher description alone is not promoted to an inspected schema.

## NEEDED — unresolved essentials

| Gap | Current state and consequence |
|---|---|
| Official AYNA stop-to-route relationships | **Unavailable for this project.** No official stop identifier/route identifier relation or stop sequence is present in inspected inputs. OSM `route_ref` and route proximity are not substitutes. Do not fabricate served routes, stop order, frequency or stop-level demand. |
| Official validation of ordinary Baku stops | OSM provides provisional positions. Official AYNA identity, active status and completeness are unresolved; the 69 terminal points do not resolve this gap. |
| Official population benchmark reconciliation | The provisional WorldPop Baku sum differs from the reported official benchmark. Obtain the benchmark's exact value, source, year, population definition and geographic scope before asserting a quantitative discrepancy or a validated population denominator. |
| Constrained population mask interpretation | Only 46.1% of in-polygon pixel centers are valid. Investigate documented product semantics and study-area fit; NoData must not automatically become zero. |
| Original AYNA provenance and usage terms | Confirm provider/source, license, acquisition date, vintage, completeness and operational status for all four originals; the inspected metadata does not establish them. |
| Bicycle-point meanings and operation | Resolve `MPS-*` versus `MPV-*` and active/planned status before using the points as operational stations or scoring inputs. |
| Validated route identifiers for demand joins | Exact source-matched joins between original route labels and BakuBus labels remain unresolved; not every route belongs to BakuBus. |
| Pedestrian network for walking-distance claims | Only a driving graph is acquired in the repository. A suitable walk network and its coverage must be validated before reporting network walking distances. |

## Population interpretation gate

- **Provisional Baku sum: 2,898,185**, rounded from 2,898,185.146993; not an official census total or predicted ridership.
- Read-only verification used the native raster and pixel-center selection (`all_touched=False`): 148,659 valid pixels / 322,482 in-polygon pixel centers = **46.1% valid pixels inside the study polygon**.
- This denominator is not the whole-country raster and the percentage is not population coverage. Full raster-footprint overlap and valid-pixel coverage are different measures.
- NoData −99999 is distinct from valid zero. Do not fill masked pixels with zero, inflate the sum to compensate for the mask or silently treat the total as complete.
- The total differs from the reported official benchmark and requires careful interpretation. Benchmark details are not established in the inspected project files; year, boundary, population concept and model/mask semantics require reconciliation. No cause of the difference or discrepancy percentage has been proven.
- `04_audit_population.py` validates the country raster and footprint overlap; it does not export or calculate a Baku population sum. The Baku calculation above was reproduced read-only for documentation, with no new derived file.

## OPTIONAL — candidates requiring verification

- Confirmed service schedules/frequency or GTFS, if obtainable with documented provenance; no availability or schema is currently asserted.
- Authoritative destination POIs, schools and universities, after coordinate, scope and usage-term validation.
- Supplementary OSM cycleways, after checking relevance, duplicates and operating status against the original lane files.
- Historical metro entries for comparable periods, if source and definitions can be validated.
- Alternative population products or official spatial population evidence to investigate the benchmark difference; do not automatically replace the acquired WorldPop source.

## REJECTED — specified uses

| Input or interpretation | Rejected use and reason |
|---|---|
| `map(1).geojson` terminal points | Rejected as an ordinary local bus-stop layer; retain as HAVE for terminal POI context. |
| Ten sightseeing examples in the bicycle-point KMZ | Rejected for Baku mobility analysis; preserve them in the untouched original. |
| OSM stop tags or nearest route lines | Rejected as proof of official AYNA stop-to-route relationships or stop-level passenger demand. |
| BakuBus route/day counts | Rejected as stop-level boardings or unique riders; retain for route-level context. |
| Metro station entries | Rejected as origin–destination trips or exits. |
| Driving graph | Rejected as a pedestrian accessibility network. |
| Automatic NoData-to-zero substitution | Rejected as a population interpretation; masked/unavailable values remain distinct from observed zero. |
| Unqualified WorldPop Baku total | Rejected as a reconciled official benchmark or complete validated denominator while the mask and benchmark differences remain unresolved. |

## Preservation and downstream rules

This inventory does not authorize processing or contract changes. Preserve raw
files, scripts and Shared Contract V1. Existing audit files are not final frontend
exports. Future exports must follow the agreed contract: EPSG:4326, `[longitude,
latitude]`, exposed distances in meters, higher priority meaning greater unmet
need, and `null` for unavailable values. Unknown fields, service relationships,
licenses, dates and completeness must not be guessed.

## Integrated-workspace release addendum — 2026-10-21

The current integrated workspace has the completed processed layers, scored grid,
recommendations, scenarios and complete export package. The raw directory in this
workspace contains only `.gitkeep`; source inputs described above are not shipped
with a clone. Their earlier inspection does not establish that those raw bytes
are now present at the processing scripts' expected locations.

| Current local processed/export artifact | Observed records |
| --- | ---: |
| Scored grid | 35,029 (19,112 known-population; 15,917 unknown-population) |
| Normalized stops / route features / metro stations / cycleways | 1,414 / 243 / 27 / 60 |
| Bus / bicycle recommendations | 20 / 14 |
| Individual accessibility scenarios | 34 (20 bus; 14 bicycle) |
| Bicycle study network | 80,957 nodes; 155,944 directed edges, recorded in study metadata |
| Complete frontend package | 7 GeoJSON layers, summary, scenarios; ZIP with README |

These are available **locally**, not permission-cleared public datasets. The
working `public/data/` contains real local overrides of older tracked mock files.
The real scenario JSON is local and ignored. Clone-safe original synthetic
fixtures are separately provided in `../demo/public/data/`.

The recommendation and simulation stages are implemented and tested. Their
methodology documents remain authoritative for the actual algorithms. Unknown
raw-source provenance, acquisition dates and redistribution terms are not
resolved by successful processing or validation. The current publication gates
are in [DATA_SOURCES.md](DATA_SOURCES.md#public-release-data-rights-audit--2026-10-21)
and [RELEASE_READINESS.md](../RELEASE_READINESS.md).
