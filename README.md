# Baku Mobility Lens

Baku Mobility Lens is an exploratory mobility accessibility project for Baku,
Azerbaijan. A Python geospatial pipeline combines mapped infrastructure, modeled
population and selected destinations to identify areas of unmet accessibility
need. A React/Leaflet interface lets users inspect those areas, review preliminary
bus-stop and bicycle-corridor candidates, and compare individual hypothetical
before/after scenarios.

This is a research prototype, not an operational transport planning service.
Accessibility is measured with **straight-line distances**, not walking routes or
journey times. Candidates have not passed field, engineering, legal-access or
safety assessments. Priority measures modeled intervention need, not certainty.

## Implemented functionality

- Population-aware bus, bicycle and overall mobility-gap scores on a 250 m grid.
- Bus-stop candidates projected onto supplied route geometry, with spacing and
  independently checked population-coverage criteria.
- Bicycle corridor candidates following eligible, directed OSM graph edges;
  existing infrastructure is excluded from proposed new geometry.
- Deterministic, independently verified single-intervention accessibility scenarios.
- Interactive infrastructure layers, priority rankings, click-based feature
  inspection, full-ID details, keyboard controls and a paginated grid browser.
- Canvas grid rendering, metric changes without rebuilding grid geometry,
  responsive panels, light/dark themes and saved before/after comparisons.
- Validated static frontend exports and a ZIP integration package.

The **local real-data snapshot**, checked on 2026-10-21, contains:

| Dataset | Features / records |
| --- | ---: |
| Analysis grid | 35,029 |
| Mapped bus stops | 1,414 |
| Supplied bus routes | 243 |
| Metro stations | 27 |
| Supplied cycleway features | 60 |
| Preliminary bus-stop candidates | 20 |
| Preliminary bicycle corridors | 14 |
| Individual scenarios | 34 (20 bus, 14 bicycle) |

These are snapshot counts, not counts in the synthetic demo or a guarantee of
complete infrastructure coverage. The real exports remain local while data
redistribution permissions are unresolved. See [release readiness](RELEASE_READINESS.md).

## Screenshots

Existing screenshots from the earlier interface are retained as historical
references; they do not show every current feature. Their underlying data and
map attribution must also pass the publication review before public release.
These externally hosted attachments are not copied into the demo assets.

<details>
<summary>Earlier map overview and feature inspector</summary>

![Earlier Baku map overview](https://github.com/user-attachments/assets/0f36f0bb-7617-416c-9297-77d26930f2e1)

![Earlier infrastructure inspector](https://github.com/user-attachments/assets/84f9e483-7d96-41b4-85c2-7ced63cb916a)

</details>

## Run the frontend from a clone

Use **Node 22.13+ within the Node 22 release line** (tested: 22.23.1, npm 10.9.8).
The locked Vite and ESLint versions impose Node engine requirements. Use the
committed lockfile; no additional mapping framework is required.

```bash
git clone https://github.com/baku-mobilitylens-team/baku-mobility-lens.git
cd baku-mobility-lens
# Until this work is merged, use the integration branch when available:
git switch integration/backend-and-scenarios
npm ci
npm run dev:demo
```

Open the local URL printed by Vite. **Synthetic demo** is visibly labeled in the
header. Its four cells, invented infrastructure, two candidates and two saved
scenario examples demonstrate the interface; none are real findings. All demo
coordinates and values were authored independently of source geometry. Saved
numbers are illustrative UI fixtures, not outputs of the spatial model.

```bash
npm test                 # Source-independent frontend unit/fixture checks
npm run lint
npm run build:demo       # Only synthetic assets; output: dist-demo/
npm run preview:demo
```

Demo mode uses `demo/public/`, ignores API configuration and never changes or
bundles the local real `public/data/`. `npm run demo:generate` reproduces only the
nine small fixtures in `demo/public/data/`. Background OSM tiles require internet
access; vector examples are local. See [demo details](demo/README.md).

`npm run dev` and `npm run build` retain the existing real/static-data workflow
and use `public/`. In a clone of the current tracked history this directory has
older mock fixtures (4 cells, 2 bus and 2 bicycle candidates) and no scenario
file. The app still renders available layers and reports saved scenarios as
unavailable; it does not invent results or substitute zero. Use the explicit demo
mode for a complete demonstration. **A normal local build may bundle rights-pending
real files: do not publish `dist/` without data clearance.**

No HTTP API server is shipped. `.env.example` defaults to static loading;
`VITE_API_BASE_URL` is only for a separately provided compatible API.

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
[FRONTEND_PERFORMANCE.md](FRONTEND_PERFORMANCE.md) and
[FRONTEND_SIMULATIONS.md](FRONTEND_SIMULATIONS.md). They are distinct from the
clone-safe `npm test` suite; real-data checks fail explicitly if inputs are absent.

## Data and processing workflow

Read [backend/AGENTS.md](backend/AGENTS.md), the dated
[data inventory](backend/DATA_INVENTORY.md),
[source/provenance and publication audit](backend/DATA_SOURCES.md), and the
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
[frontend validators](src/data/validateData.js),
[scenario validator](src/data/validateScenarios.js) and backend verifiers; this
summary does not replace or extend the contract.

## Methods and interpretation limits

- [Scoring methodology](backend/SCORING_METHODOLOGY.md): modeled need, with explicit
  uncalibrated planning weights; missing population retains null scores.
- [Bus methodology](backend/BUS_RECOMMENDATIONS_METHODOLOGY.md): straight-line
  coverage and route-proximity screening, not verified stop–route membership.
- [Bicycle methodology](backend/BIKE_RECOMMENDATIONS_METHODOLOGY.md): conservative
  tag eligibility and routing cost are not physical safety assessments. OSM
  bicycle-permissible roads are not necessarily bicycle lanes.
- [Simulation methodology](backend/SIMULATION_METHODOLOGY.md): baseline versus one
  intervention using a 500 m threshold. `population_improved` includes any modeled
  distance reduction; `newly_covered_population` counts threshold crossings.
  Coverage change is **percentage points**, using the same known-population
  denominator before and after. Separate scenario benefits may overlap and must
  never be added into a combined citywide gain.

The bicycle simulation baseline uses AYNA lanes only. Five bicycle recommendations
have additional existing-OSM coverage exclusions and therefore differ from their
saved simulation's newly covered population; the UI preserves their statuses and
limitations. Twenty bus and nine bicycle records match. The simulator's aggregate
reconciliation does not independently recheck the OSM exclusions.

WorldPop counts are modeled, with 15,917 unknown-population cells in this snapshot
and other partially covered cells. Unknown does not mean uninhabited. OSM and
supplied infrastructure can be incomplete or stale. Route/day validations are
not stop-level demand; metro entries are not origin–destination trips. Source
geometry does not demonstrate operating service, access permission, buildability
or safety. Performance measurements are local observations, not browser/device
service guarantees.

## Contributors and licensing

- [@osmanveyisli](https://github.com/osmanveyisli): backend, data engineering,
  geospatial analysis, scoring, recommendations, simulations and validation.
- [@ahaddilanov](https://github.com/ahaddilanov): frontend, React/Leaflet map,
  interface design, visualization and interaction engineering.
- Integration and testing were collaborative. See [CONTRIBUTORS.md](CONTRIBUTORS.md).

No code LICENSE is present. **MIT is proposed for both contributors' approval**;
no license has been added or inferred from repository visibility. Dependency and
data licenses are separate from the project's original code. OSM requires its
own attribution/ODbL review; WorldPop and geoBoundaries attribution/version terms
must be retained. OpenData.az and AYNA-attributed inputs need resource-specific
rights evidence. **AYNA geometry redistribution rights are not verified.
Attribution alone does not establish permission to redistribute it.** This also
requires reviewing derived exports, recommendations, screenshots and history.
See the precise blockers in [RELEASE_READINESS.md](RELEASE_READINESS.md) and
[DATA_SOURCES.md](backend/DATA_SOURCES.md#public-release-data-rights-audit--2026-10-21).

## Future improvements

Obtain and document source redistribution rights; preserve reproducible authorized
snapshots and complete environment locks; validate missing population semantics
and POI categories; incorporate verified stop–route relationships and service
frequency; compare network-based walking accessibility; assess candidate crossings,
barriers, gradients and safety in the field. Joint intervention analysis would
need a new non-additive portfolio calculation. These are future work, not
capabilities claimed by this release.
