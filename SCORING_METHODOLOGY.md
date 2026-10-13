# Baku TransportTech baseline priority scoring — v1.0

**Purpose:** Rank 250 m Baku grid cells for *further investigation* of bus and cycling accessibility interventions. Scores measure **need weighted by local demand**, not the engineering feasibility or cost of a specific project. Larger values always mean greater priority. All thresholds below are explicit **planning assumptions**, not an externally calibrated model.

## Actual data inputs

`data/processed/grid/baku_grid_pois.geojson` (35,029 grid cells) already combines WorldPop 2026 modeled population, 1,414 provisional OSM bus-stop points, 98 metro exit/entrance points, 60 AYNA bicycle-lane features and 1,751 selected destination records. Distances/counts are straight-line from each grid cell's interior representative point in EPSG:32639. Coordinates are exported in WGS84 EPSG:4326.

**Fields used now:** `population`, `valid_pixel_fraction`, `nearest_bus_stop_m`, `nearest_metro_m`, `nearest_cycleway_m`, `bus_stops_500m`, and `pois_500m_by_type`, reconciled against `pois_nearby`.

**Data restrictions:** WorldPop is modeled, not census population; 15,917 cells have `population=null` and must **not** be treated as zero. Some additional cells have only partial valid-raster coverage. OSM may omit stops and does not establish operational status or which route serves a given stop. Metro entries do not specify where riders originate or travel. AYNA route-level validations cannot be assigned to stops or neighborhoods. The selected POIs are not exhaustive and include unverified records; the category `CUSTOMIZABLE_POINT_5` mixes several types and is **not counted as verified universities**.

## Core model

Let `clamp(x) = min(1,max(0,x))` and all scores be rounded to two decimal places.

### Potential demand

- Residential population index: `P = clamp(population / 400)`; 400 modeled residents per 250 m cell is the documented starting saturation threshold.
- Essential destinations index: `E = clamp((2*schools + 2*hospitals + 1*kindergartens + 0.5*pharmacies)/6)` where the inputs are counts within an inclusive straight-line 500 m radius. Schools/hospitals receive higher *assumed* trip-attraction weights; the mixed-category institutions are deliberately omitted until classified.
- Combined potential-demand index: **`D = 0.70*P + 0.30*E`**.

A cell with observed zero population can still have demand from a nearby school or hospital. A cell with zero population and zero selected POIs scores zero. A cell whose population is unknown receives **null** priority scores rather than an invented demand value. Partial population coverage is reported with `scoring_quality`; unknown raster cells are never filled with zero.

### Bus need

- Distance deficit: `Bd = clamp((nearest_bus_stop_m - 250) / 750)`; deficit zero at <=250 m, full at >=1000 m.
- Stop scarcity: `Bs = clamp(1 - bus_stops_500m / 2)`; zero nearby stops scores 1, one scores 0.5, two or more scores 0.
- Bus access deficit: **`B = 0.85*Bd + 0.15*Bs`**.
- **`bus_priority = 100*D*B`**.

Stop scarcity contributes relatively little because its relationship with nearest-stop distance partly overlaps. This measures mapped stop proximity and redundancy, **not frequency, travel time, route diversity or reliable service**.

### Bicycle need

- Bicycle-lane deficit: `C = clamp((nearest_cycleway_m - 250) / 2750)`; zero at <=250 m, full at >=3000 m.
- **`bike_priority = 100*D*C`**.

The model does not claim that all mapped lanes are safe/connected/operational. Distances to existing facilities identify unmet infrastructure proximity; they do not prove a feasible corridor can be built. In peripheral areas the bicycle deficit saturates, so the demand index—not arbitrary additional distance—distinguishes cells.

### Combined mobility gap

- Metro proximity deficit: `M = clamp((nearest_metro_m - 500) / 2500)`; zero at <=500 m, full at >=3000 m, measured to metro **entrances**.
- **`mobility_gap = 100*D*(0.50*B + 0.30*C + 0.20*M)`**.

This is a **demand-weighted mobility gap**, not a physical accessibility measurement independent of population. It gives the bus network greatest weight because our scope emphasizes bus/first-last-mile planning, but those weights are judgments rather than empirical causal estimates.

## What is deliberately NOT in this score

| Available or prospective information | Reason for exclusion from baseline need | Appropriate later use |
|---|---|---|
| AYNA route geometry | A route line passing nearby does not prove a bus serves a mapped stop | Candidate-stop *feasibility/context*, matched with existing road corridors |
| BakuBus route-level payment validations | Only 63 exact route-label matches; no stop-level boardings or alightings | Route-level context after confirmed stop–route relationship; never transfer counts to all route-side cells |
| Metro station daily entries | Entries are neither origins nor unique passengers | Transit-hub context and possible bike-first/last-mile opportunities |
| Driving network | Motor vehicle topology is not verified pedestrian accessibility | Check physically plausible candidate stop placement; replace straight-line measurement only after a walking network exists |
| `CUSTOMIZABLE_POINT_5` mixed POIs | Cannot reliably identify all 69 as universities | Clean/verify categories, then add an explicit university weight |
| Missing population | No valid population pixels; cannot assume an empty area | Keep scores null and flag for further data collection |

## Data confidence and interpretation

The script writes `scoring_quality` (`unknown_population`, `low_population_pixel_coverage`, `partial_population_pixel_coverage`, `full_population_pixel_coverage`, or `population_coverage_unreported`). These **do not multiply down scores**: suppressing a potentially underserved place for lack of data would be misleading. Review high-ranking partial-coverage cells manually before recommending interventions. POI classifications/operational status and OSM service coverage are independent uncertainties that the cell-level file cannot yet quantify.

Scores should be used to **rank and shortlist** areas. They do not demonstrate a specific bus stop or bike corridor is legal, safe, connected, operationally useful or cost-effective. A later **candidate feasibility stage** should evaluate real AYNA route lines, OSM road geometry, current stop separation, access to nearby lanes and engineering exclusions, and should always call bike corridors *candidates for further engineering assessment*.

## Extensibility and reproducibility

All starting parameters live in `config/scoring_v1.json` and carry `model_version`; the output stores its configuration hash. Keep this file unchanged after reporting v1 results. For new parameters or sources, make a new `scoring_v2.json`, change the version, rerun from the affected processing stage, and **compare both versions**. This prevents a quiet change in rankings masquerading as an input update.

- **New schools/hospitals/universities:** update `12_process_pois.py`, document exact taxonomy and license, rerun POI counts and scoring. A verified university category can be added to `poi_weights` with a documented source change.
- **More accurate bus stops:** rerun bus-stop normalization, accessibility, POI preservation/merge, and scoring; never overwrite the earlier score version silently.
- **Official route–stop mapping:** store a distinct directional `route_id, direction_id, stop_order, stop_id` relationship. Derive optional `nearest_verified_served_stop_m` and `routes_serving_stops_500m`; **do not repurpose** `nearest_bus_stop_m` or `bus_routes_nearby` without an explicit definition/contract update.
- **Walking network:** build/verify OSM pedestrian topology and quantify network versus straight-line differences. Add new `walking_distance_*` fields; keep original straight-line measurements for baseline comparisons.
- **Additional destination/traffic data:** audit provenance, license, CRS, coverage, definitions and missingness, then add a new factor or optional candidate criterion only when it can be justified across the study region.

If new data covers only a subset of routes/neighborhoods, do not implicitly give zero credit to all other areas. Prefer a separate *data confidence* signal, a scoped model, or wait until region-wide evidence is sufficient for fair city-wide score comparisons. Do not renormalize available weights on a per-cell basis without clearly stating that scores have different meanings.

## Validation and sensitivity checks before presentation

1. Check all 35,029 IDs and geometries preserved; null population -> all three null scores; zero population plus zero POIs -> all three zero.
2. Check 0–100 numeric bounds and monotonicity: increasing population, POIs or physical access deficit alone must not lower the relevant priority, holding all other factors fixed. Scores must never be based on route-level validations treated as local boardings.
3. Inspect top-ranked cells, especially peripheral or partially sampled cells. Review mapped stop accuracy and important POI names visually where feasible.
4. Try population saturation at 250/400/600, bus severe distance at 750/1000/1250 m, and POI weights +/-25%; report whether the top-ranked *areas* are robust. A fixed threshold such as score >=60 is **only a reporting threshold**, not a statistically derived high-priority cutoff.
5. Population-weighted coverage figures must use valid population and a disclosed denominator; the percentage of **grid cells** within 500 m is not the percentage of **people** within 500 m.
6. If changes to the scoring model's weights are made, record model version and data retrieval dates in `DATA_SOURCES.md`/`SCORING_METHODOLOGY.md`.
