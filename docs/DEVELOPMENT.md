# Development and reproducibility

Commands are run from the repository root unless a `cd backend` step is shown.
See the [project overview](../README.md) for the synthetic demo and licensing.

## Backend setup and tests

The backend is a file-based Python geospatial pipeline. Python **3.14.7** was used
for this release audit. Native GDAL/PROJ/GEOS availability and compatible wheels
matter; other Python/platform combinations have not been verified here.

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

The four directly pinned packages are OSMnx 2.1.1, GeoPandas 1.2.0, Pyogrio 0.13.0
and Rasterio 1.5.2; their dependencies provide Shapely, PyProj, NumPy, NetworkX and
other libraries. Direct requirements are pinned, but a complete transitive/native
platform lock is not supplied. The unit tests create temporary synthetic inputs
and do not require downloading the Baku source datasets or contacting OSM.

For the frontend's full-snapshot consistency checks, an authorized developer
with the complete real files can run `npm run test:real-data` from the project
root. The browser interaction, simulation and zoom scripts also require that
snapshot, Node 22+, an isolated Chrome debugging session and the local development
server. Exact commands and previous measured performance are in
[FRONTEND_PERFORMANCE.md](../FRONTEND_PERFORMANCE.md) and
[FRONTEND_SIMULATIONS.md](../FRONTEND_SIMULATIONS.md). They are distinct from the
clone-safe `npm test` suite; real-data checks fail explicitly if inputs are absent.

## Data and processing workflow

Read [backend/AGENTS.md](../backend/AGENTS.md), the dated
[data inventory](../backend/DATA_INVENTORY.md),
[source/provenance and publication audit](../backend/DATA_SOURCES.md), and the
methodologies before running processing. Paths below are relative to `backend/`.
Raw, processed and export files are intentionally excluded from Git, apart from
empty-directory markers. The source inventory's early inspection is historical;
its release addendum describes the current processed-data availability.

A fresh clone **cannot reproduce the complete Baku analysis by itself**. Obtain
permission and the original source versions, verify their provenance/checksums,
and place them at the paths expected by the existing scripts:

| Required source | Expected raw location / acquisition |
| --- | --- |
| Baku boundary | `scripts/01_download_boundary.py` retrieves the pinned geoBoundaries source |
| Provisional OSM stops | `scripts/03_audit_bus_stops.py` queries OSM after the boundary exists |
| WorldPop 2026 constrained raster | `scripts/04_audit_population.py`; exact URL/hash in DATA_SOURCES.md |
| AYNA-attributed bus lines | Authorized `data/raw/ayna/buslines(1).kmz` |
| AYNA-attributed bicycle lanes | Authorized `data/raw/ayna/movcud-zolaqlar-velo(1).kmz` |
| Route/day validations | Authorized `data/raw/opendata/bakubus_passenger-2026.csv` |
| Metro entrances and station entries | Authorized `data/raw/opendata/pathways.csv` and `passenger-2026.csv` |
| Selected destination source | Authorized `data/raw/opendata/azrbaycanda_obyektlr_v_mkanlar.geojson` |

OpenData publisher references are recorded in DATA_SOURCES.md; they do not prove
that every locally supplied file has identical contents or redistribution terms.
AYNA originals need provider permission/provenance confirmation; there is no
verified public acquisition URL for those supplied versions. Do not substitute
terminal points for ordinary bus stops. Live OSM queries can differ from the
original snapshot; preserve authorized originals and caches for repeatability.

The processing order is explicit in the existing scripts:

| Stage | Scripts | Result |
| --- | --- | --- |
| Acquisition/audits | `01` boundary, `02` driving graph, `03` stops, `04` population | Raw inputs and boundary; driving graph is separate context |
| Infrastructure | `05_process_bus_stops.py` through `09_process_metro.py` | Normalized stops, routes, route-level demand, lanes, metro |
| Analysis | `10_build_population_grid.py`, `11_calculate_accessibility.py`, `12_process_pois.py`, `13_calculate_priority.py` | Population, proximity, destinations, scored grid |
| Bus candidates | `14_recommend_bus_stops.py` | Preliminary stop candidates |
| Bicycle network/candidates | `15_build_bike_network.py`, `16_recommend_bike_corridors.py` | Study network and directed-path candidates |
| Scenarios | `17_simulate_accessibility.py` | Independent before/after comparisons |
| Frontend package | `18_export_frontend_complete.py` | Validated compact layers, summary, scenarios and ZIP |

Run only the necessary stage after its inputs are supplied, for example
`python scripts/13_calculate_priority.py`. Acquisition scripts contact external
services; do not rerun them to inspect existing results. Existing `--verify-only`
commands validate saved artifacts without rebuilding them. The older
`export_frontend_baseline.py` remains available and is reused by the complete
exporter; it is not the complete recommendation/scenario package.

With authorized processed inputs and saved scenarios, from `backend/`:

```bash
# Offline validation of already saved results
python scripts/17_simulate_accessibility.py --verify-only
python scripts/18_export_frontend_complete.py --verify-only

# Generate a new validated export package only when required
python scripts/18_export_frontend_complete.py
python scripts/18_export_frontend_complete.py --verify-only
```

The exporter writes `data/exports/complete/` and
`data/exports/frontend_complete.zip` using staging, independent checks and
replacement/rollback handling. It does not modify `public/data/`. The ZIP contains
nine files under `data/` plus a README. After rights clearance, extract it into a
**separate review directory**, check counts, IDs, attribution and scenarios, then
intentionally integrate it into a private/authorized frontend workspace. Never
unzip blindly over the synthetic demo or stage real exports while rights remain
unresolved. Historical exporter metadata still says the scenario UI was not wired;
that note describes export-time integration, and the frontend now implements it.

## Architecture and technology

```text
src/                      React interface, Leaflet layers, validation and formatting
public/data/              Legacy tracked mocks / local real static overrides
demo/public/data/         Small original synthetic UI fixtures
scripts/create_demo_data.mjs  Deterministic demo-fixture generator
tests/                    Frontend unit and real-data browser/consistency checks
backend/scripts/          Acquisition, normalization, analysis and export stages
backend/config/           Versioned baseline scoring parameters
backend/tests/            Offline synthetic backend unit/regression tests
backend/data/raw/         Local source inputs (ignored)
backend/data/processed/   Local validated analysis artifacts and networks (ignored)
backend/data/exports/     Local integration packages (ignored)
```

React 19, React-Leaflet 5, Leaflet 1.9.4 and Vite 8 provide the frontend; ESLint and
Node's built-in test runner provide frontend checks. Python, GeoPandas, Shapely,
PyProj, Rasterio, OSMnx and NetworkX implement geometry, raster processing and
routing. The application reads static files; it does not run a Python service in
the browser or calculate new scenarios client-side.

## Shared GeoJSON Contract V1

Contract fields are unchanged. GeoJSON FeatureCollections use EPSG:4326 and
`[longitude, latitude]`; metric geometry is calculated in EPSG:32639. Distances
exposed to the interface are meters. IDs remain complete strings. Scores range
from 0–100, with larger values meaning greater intervention need. `null` means
unavailable and must remain distinct from observed zero. Presentation rounding
does not change stored values.

| Record | Required properties |
| --- | --- |
| Grid | `id`, `population`, `nearest_bus_stop_m`, `nearest_metro_m`, `nearest_cycleway_m`, `bus_stops_500m`, `bus_routes_nearby`, `pois_nearby`, `bus_priority`, `bike_priority`, `mobility_gap` |
| Bus stop | `id`, `name` |
| Bus route | `id`, `name`, `route_ref`, `avg_daily_validations` |
| Metro station | `id`, `name`, `avg_daily_entries` |
| Cycleway | `id`, `name`, `length_m` |
| Bus candidate | `id`, `priority`, `population_affected`, `current_access_m`, `new_access_m`, `access_improvement_m`, `reason` |
| Bicycle candidate | `id`, `priority`, `length_m`, `population_coverage_gain`, `start_name`, `end_name`, `reason` |
| Summary | `generated_at`, `grid_cells`, `population_estimate`, `high_bus_priority_cells`, `high_bike_priority_cells` |
| Simulation | `intervention_id`, `intervention_type`, `population_improved`, `coverage_before_pct`, `coverage_after_pct`, `coverage_change_pp`, `avg_access_improvement_m`, `affected_cells` |

Recommendation `reason` is an array of strings. Simulation JSON is an object
with `metadata`, `summary` and a `scenarios` array, not a bare array. Types,
nullability, geometry rules and optional metadata are implemented in the existing
[frontend validators](../src/data/validateData.js),
[scenario validator](../src/data/validateScenarios.js) and backend verifiers; this
summary does not replace or extend the contract.

