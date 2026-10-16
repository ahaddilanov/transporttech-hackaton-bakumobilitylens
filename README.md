# Baku Mobility Lens

**Built for TransportTech Hackathon · Baku, Azerbaijan**

Baku Mobility Lens is an interactive geospatial decision-support tool for exploring public-transport and cycling accessibility across Baku. It combines a city-scale analysis grid with real transport infrastructure so users can see **where mobility gaps are concentrated, how severe they are, and why an area receives a particular priority score**.

Built together with my friend **Osman**, this project connects a geospatial data-analysis backend with a React + Leaflet frontend designed for clear, fast exploration of real Baku mobility data.

# City-scale mobility overview
<img width="1278" height="731" alt="Screenshot 2026-10-17 001736" src="https://github.com/user-attachments/assets/0f36f0bb-7617-416c-9297-77d26930f2e1" />


## What the project does

The application brings several parts of Baku's mobility system into one map-first interface:

- visualizes **mobility gap**, **bus priority**, and **cycling priority** across the analysis grid;
- displays mapped **bus stops, bus routes, metro stations, and cycleways**;
- lets users click grid cells and transport features to inspect the underlying data;
- shows city-level baseline statistics at a glance;
- preserves missing values correctly — `null` means unavailable, not zero;
- keeps higher scores visually consistent with **greater intervention need**;
- supports light/dark themes, collapsible panels, map focus mode, and a Baku overview;
- is prepared for later recommendation and before/after simulation layers when those backend datasets are ready.

The goal is not to produce a generic smart-city dashboard. The interface is designed around a simple planning story:

> **Where is the mobility problem? How serious is it? Why was this area flagged? What should be investigated next?**

## Real baseline data

The current frontend uses the first real integrated Baku baseline rather than development mocks.

| Dataset | Current baseline |
|---|---:|
| Analysis grid | **35,029 cells** |
| Mapped bus stops | **1,414** |
| Bus route geometries | **243** |
| Metro stations | **27** |
| Mapped cycleway features | **60** |
| Available modeled population estimate | **~2.90 million** |
| Cells with unknown modeled population | **15,917** |
| Backend high-bus-priority cells (`score >= 60`) | **416** |
| Backend high-cycling-priority cells (`score >= 60`) | **1,948** |

The population figure is a modeled estimate from available data, not a census total.

## Interface walkthrough

### Explore the city at a glance

The main screen keeps the map central while presenting the city summary and analytical controls around it. Users can compare mobility conditions across the wider Baku study area without leaving the map. The interface supports both light and dark modes.

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/c114ce34-e49b-4f5e-ae44-395bf7e8f0d3"
    alt="Baku Mobility Lens city overview"
    width="82%"
  />
</p>

### Inspect existing transport infrastructure

Bus stops, routes, metro stations, and cycleways are interactive. Selecting a feature opens the inspector without losing map context.

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/84f9e483-7d96-41b4-85c2-7ced63cb916a"
    alt="Baku Mobility Lens infrastructure inspector"
    width="78%"
  />
</p>

Route-level validation values remain **route-level context**. The frontend never treats them as stop-level ridership and does not invent stop-to-route relationships.

### Understand why a grid cell is important

Selecting an analysis cell exposes the measurements behind its map color: population context, distances to transport infrastructure, nearby POIs, priority scores, and data-quality information when available.

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/b18139c7-b744-4bfd-9e64-dac4c9e1c432"
    alt="Baku Mobility Lens grid-cell analysis"
    width="78%"
  />
</p>

This makes the score explainable rather than presenting a heatmap with no context.

### Control the map layers

Existing infrastructure and analytical layers are separated clearly so users can distinguish what is physically mapped from what the model is evaluating.

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/800124f5-670f-4575-991f-c6f326df8716"
    alt="Baku Mobility Lens layer controls"
    width="30%"
  />
</p>

## Priority scores

All priority metrics use a `0–100` scale where **higher always means greater need for further investigation**.

| Score | Frontend meaning |
|---:|---|
| `0–24` | Low need |
| `25–49` | Moderate need |
| `50–74` | High need |
| `75–100` | Very high need |
| `null` | Unavailable / missing |

A real score of `0` is valid data. A `null` score is not zero and is shown separately.

The backend baseline uses `score >= 60` as a reporting threshold for its summary counts. That reporting rule is separate from the four visual bands shown in the frontend legend.

These scores indicate analytical priority. They are **not construction-readiness scores, engineering approvals, or measures of infrastructure quality**.

## Technology stack

| Area | Technology |
|---|---|
| Frontend | React 19 |
| Development/build | Vite 8 |
| Mapping | Leaflet 1.9 + React-Leaflet 5 |
| Geospatial exchange | GeoJSON |
| Basemap | OpenStreetMap |
| Styling | Custom CSS |
| Coordinate system | WGS84 / EPSG:4326 |

The frontend intentionally keeps dependencies small and avoids heavyweight UI or state-management frameworks.

## Frontend ↔ backend architecture

The project is split so each side has a clear responsibility.

**Backend / data / analysis**

- data collection and cleaning;
- spatial and accessibility analysis;
- population and destination context;
- priority-score generation;
- exported GeoJSON/JSON;
- future recommendation and simulation outputs.

**Frontend / map / UI**

- map rendering;
- layer controls;
- score visualization;
- feature selection and inspection;
- summary cards;
- responsiveness and themes;
- safe null handling;
- large-grid performance;
- integration of backend outputs.

The frontend does not recompute the backend's major geospatial analysis.

## Shared data contract

Frontend-facing geospatial data follows a strict contract:

```text
Format:       GeoJSON
CRS:          WGS84 / EPSG:4326
Coordinates:  [longitude, latitude]
Distances:    meters
Missing data: JSON null
IDs:          strings
Scores:       0–100
```

Current baseline files:

```text
grid.geojson
bus_stops.geojson
bus_routes.geojson
metro_stations.geojson
cycleways.geojson
summary.json
```

The frontend does not silently rename required backend properties.

## Performance with the real grid

The first prototype only needed a few mock grid cells. The real dataset contains **35,029 polygons**, so the rendering strategy had to change without rebuilding the UI.

For the real baseline integration:

- the analysis grid uses a dedicated **Leaflet Canvas renderer**;
- grid interaction remains available at cell level;
- tooltips are created lazily instead of creating tens of thousands at startup;
- infrastructure layers remain normal interactive vectors;
- changing Overall / Bus / Cycling changes presentation rather than rerunning geospatial analysis in the browser.

This allowed the same interface to scale from a development mock to a real city-scale baseline.

## Data interpretation and limitations

The project deliberately avoids presenting analytical outputs with more certainty than the data supports.

- Missing values are displayed as unavailable rather than converted to zero.
- Accessibility distances in the baseline are not necessarily walking-network travel distances.
- `avg_daily_validations` is route-level payment-validation context, never stop-level passenger demand.
- Metro entry averages are not OD trips or counts of unique passengers.
- Mapped stops, routes, POIs, and cycleways may not be exhaustive.
- A high priority score means an area deserves further investigation; it does not automatically mean an intervention is feasible.
- Future bicycle recommendations will be presented as **candidate corridors for further engineering assessment**, not construction-ready plans.

## Data sources

The baseline uses data derived from or attributed to sources including:

- **geoBoundaries** — Baku study-area boundary;
- **WorldPop** — modeled population counts;
- **OpenStreetMap contributors** — mapped bus stops and map context;
- **AYNA-attributed linework** — route and bicycle-lane geometry;
- **OpenData.az / BakuBus context** — available route-level validation averages;
- **Baku Metro data** — station-entry averages and station/entrance context.

Source-specific licenses, provenance, vintage, completeness, and attribution requirements remain with their original providers.

## Run the frontend locally

Requirements: Node.js, npm, and Git.

```bash
git clone <your-repository-url>
cd <your-repository-folder>
npm ci
npm run dev
```

Open the local URL printed by Vite, normally:

```text
http://localhost:5173
```

Quality checks:

```bash
npm run lint
npm run build
```

Production preview:

```bash
npm run preview
```

## Current status

| Feature | Status |
|---|:---:|
| Interactive Baku map | ✅ |
| Real 35,029-cell analysis grid | ✅ |
| Bus stops | ✅ |
| Bus routes | ✅ |
| Metro stations | ✅ |
| Cycleways | ✅ |
| Mobility-gap view | ✅ |
| Bus-priority view | ✅ |
| Cycling-priority view | ✅ |
| Feature inspector | ✅ |
| Grid-cell inspector | ✅ |
| Baseline summary | ✅ |
| Null-safe rendering | ✅ |
| Light / dark themes | ✅ |
| Large-grid rendering optimization | ✅ |
| Real bus recommendations | ⏳ Backend dataset pending |
| Real bicycle candidate corridors | ⏳ Backend dataset pending |
| Before / after simulation | ⏳ Future integration |

## Next steps

1. Integrate real candidate public-transport improvements.
2. Integrate bicycle candidate corridors for further engineering assessment.
3. Show backend-generated reasons for each recommendation.
4. Connect optional API delivery.
5. Add before/after intervention results when simulation outputs exist.
6. Complete final source-credit and attribution review.
7. Prepare the final hackathon demo and portfolio deployment.

## Team

Baku Mobility Lens was built as a collaborative TransportTech Hackathon project.

I developed the **frontend / map / UI** side of the project, while my friend **Osman** worked on the **backend / data / analysis** side. Integration is shared through the project's explicit GeoJSON/JSON contract.

That split allowed us to work independently while keeping geometry, field names, units, null handling, and score meaning consistent across the system.

## What this project demonstrates

For us, Baku Mobility Lens is more than a map. It demonstrates the process of taking an idea from a small prototype to a real-data system:

- collaborative frontend/backend development;
- geospatial-data integration;
- interactive map engineering;
- UI/UX design for analytical tools;
- performance optimization for tens of thousands of polygons;
- transparent handling of missing and uncertain data;
- transport-data interpretation;
- contract-based integration;
- debugging, testing, and iterative refinement.

The result is a working prototype that makes complex mobility data easier to explore and easier to explain.

---

## Baku Mobility Lens

**Making mobility gaps visible — and transport priorities easier to understand.**

*TransportTech Hackathon · Baku, Azerbaijan*
