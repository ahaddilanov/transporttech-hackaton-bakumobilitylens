# Preliminary Baku bus-stop recommendations — Step 16A

Method version: `baku-bus-recommendations-v1.0`.

These are locations for further investigation, with hypothetical gains in
proximity to a mapped bus stop. They are not approved stop locations, ridership
forecasts, verified service improvements or engineering designs. Baseline v1
scoring and Shared Contract V1 remain unchanged.

## Inputs inspected

All four local inputs are EPSG:4326. The script validates their actual fields,
geometry types, finite coordinates, IDs and mandatory nonempty layers before
processing. It prints complete observed property lists and records source-file
SHA-256 hashes in output metadata. No source features are silently filtered,
repaired, relabeled or overwritten.

| Input under `data/processed/` | Observed features | Fields used |
| --- | ---: | --- |
| `grid/baku_grid_scored.geojson` | 35,029: 35,028 Polygons and 1 MultiPolygon | `id`, `population`, `bus_priority`, `nearest_bus_stop_m`, `valid_pixel_fraction`, geometry |
| `transport/bus_routes_with_demand.geojson` | 243: 236 LineStrings and 7 MultiLineStrings | `id`, `source=AYNA`, `route_ref`, geometry |
| `transport/bus_stops.geojson` | 1,414 Points | `id`, geometry |
| `boundaries/baku_boundary.geojson` | 1 MultiPolygon, `shapeName=Baku City` | `shapeID`, `shapeName`, geometry |

The grid has 19,112 cells with known modeled population and 15,917 with null
population. Null means unavailable, never zero. Partial raster coverage remains
the observed modeled population sum; it is not extrapolated to missing pixels.
See [SCORING_METHODOLOGY.md](SCORING_METHODOLOGY.md) and
[DATA_SOURCES.md](DATA_SOURCES.md) for baseline definitions and source caveats.

The route file contains `avg_daily_validations` and other demand-join fields.
None of those fields is used for seed selection, coverage, priority or ranking.
BakuBus validations are route-level electronic-payment events and cannot be
interpreted as stop-level demand. `route_ref` is copied as geometric context;
it does not assert verified stop-route membership, direction or active service.

## Geometry and fixed screening thresholds

Every calculation uses planar meters in **EPSG:32639**. Each grid origin is its
interior `representative_point()` after projection, matching the baseline
accessibility convention. Origins are neither population-weighted locations nor
walking-network nodes. The script checks that stored `nearest_bus_stop_m` agrees
with the current mapped-stop layer within 0.000001 m; stale inputs fail explicitly.

1. Select every cell with non-null population and `bus_priority >= 60`.
   Known zero population is eligible as a seed; it cannot itself supply residents.
2. Split the actual AYNA geometries into their original LineString parts for
   indexing, retaining source feature ID, zero-based part index and route label.
   A Shapely STRtree finds the nearest full route line part to each seed origin.
   All exact nearest ties are resolved by ascending `(route feature ID, part index)`.
   No route vertices, centroids or invented route corridors substitute for lines.
3. Reject the seed if its shortest distance to that line is **greater than 300 m**.
   Otherwise project the origin onto the line with
   `line.interpolate(line.project(origin))`. One candidate is evaluated per seed;
   a rejected nearest projection is not replaced with another route or position.
4. Convert the projected point to EPSG:4326 and back to EPSG:32639, so subsequent
   coverage and spacing use the exact exported position. Require the location
   strictly inside both the projected and original Baku polygon. Boundary edges,
   holes and locations outside the polygon fail; no boundary buffer is used.
5. Require shortest straight-line distance to **any mapped existing bus stop
   >= 300 m**, using a stop spatial index. No route membership is presumed.
6. Evaluate coverage below and reject if the gain in known modeled population
   is zero. Do not relax any threshold when few or no candidates qualify.

Output is Point GeoJSON in **EPSG:4326**, with `[longitude, latitude]` coordinates.
Screening uses the fixed inequalities above without tolerance buffers. Independent
verification allows at most 0.000001 m for projection/GEOS roundoff in point-on-line
and spacing checks; that is not a planning-threshold relaxation.

## Hypothetical coverage and population-weighted access

For **every grid cell**, including cells that were not eligible seeds, let:

- `b_i = nearest_bus_stop_m` from the unchanged baseline;
- `d_i` = straight-line distance from the cell's representative point to the
  hypothetical candidate;
- `a_i = min(b_i, d_i)`.

A cell is newly covered exactly when **`b_i > 500` and `a_i <= 500`**. Baseline
distance exactly 500 m is already covered. A new distance exactly 500 m qualifies.
This is a cell-origin approximation: it does not model the population's distribution
within a cell, paths, crossings, barriers or passenger decisions.

Let `K` be newly covered cells with non-null population `p_i`. Then:

```text
population_affected   = sum(p_i for i in K)
current_access_m      = sum(p_i * b_i for i in K) / population_affected
new_access_m          = sum(p_i * a_i for i in K) / population_affected
access_improvement_m  = current_access_m - new_access_m
```

These are means over **newly covered residents only**. Already covered residents
and residents whose access improves but remains beyond 500 m are excluded.
Known zero-population cells may count as newly covered cells, but have zero weight.
A candidate with no positive known-population coverage is rejected; no undefined
mean or invented population value is exported. Values remain unrounded JSON
numbers, including fractional modeled residents; no census calibration is applied.

`newly_covered_cells` counts `K`, including observed zero-population cells.
`unknown_population_cells` separately counts null-population cells satisfying the
same geometric newly-covered test. Their resident counts and weighted means remain
unknown and are never imputed. `population_quality_notes` records:

- that population is modeled, rather than census population or ridership;
- the number of newly covered unknown-population cells excluded;
- the number of newly covered known-population cells with `valid_pixel_fraction < 1`;
- the number with unreported valid-pixel coverage.

Top-level `population_summary` reports known and unknown cells across the whole grid.
Quality counts are cell counts, not percentages of residents or area.

Each proposal is measured **independently against the original baseline**.
The 700 m spacing does not eliminate overlapping 500 m coverage areas. Benefits
across proposals must not be summed as unique residents, and this stage is not a
joint network or incremental portfolio optimization.

## Exact ranking, spacing and stable identity

The Contract V1 `priority` is the seed's **unchanged `bus_priority`**, in [0,100].
It continues to mean local intervention need. The selection rank is a separate,
explicit lexicographic ordering, not a newly calibrated priority score.

Sort eligible candidates in ascending order by this tuple, using unrounded values:

```text
(-population_affected,
 -priority,
 -access_improvement_m,
 source_grid_id,
 nearby_route_id,
 route_part_index)
```

Thus greater measured newly covered population wins first, stronger local priority
wins an equal-coverage tie, then greater mean access improvement, followed by stable
source identifiers. No validation counts or arbitrary population-normalization
thresholds enter ranking.

Walk the sorted list, retaining a candidate only if its Point is **at least 700 m**
from every previously retained candidate. This is greedy spatial suppression,
not connected-component clustering: a rejected point does not suppress others.
Process the whole list to report duplicates, then keep the first **at most 20**
retained candidates. `qualified_beyond_limit` counts the retained candidates omitted
by the cap. Fewer qualifying locations produce fewer recommendations.

IDs have the prefix `baku:bus-stop-recommendation:` followed by full SHA-256 of
the UTF-8 compact JSON array:

```text
[method_version, source_grid_id, nearby_route_id, route_part_index,
 projected_easting_formatted_to_6_decimals, projected_northing_formatted_to_6_decimals]
```

Coordinates in the ID payload are the original projection in EPSG:32639; six
decimals denote micrometers, not output rounding. IDs contain no recommendation
rank or input-array position. Identical sources and method reproduce IDs and
output bytes; reordering source features does not change proposal IDs. Changes
to a seed, chosen route part, projected location or method version may change IDs.
These IDs are project identifiers, not official stop identifiers.

## Output fields and verification

`data/processed/recommendations/bus_recommendations.geojson` is a FeatureCollection
with these existing Contract V1 properties on every Point:

| Property | Exported meaning/type |
| --- | --- |
| `id` | Stable string, also stored as feature `id` |
| `priority` | Seed bus priority, numeric 0–100 |
| `population_affected` | Positive newly covered modeled population |
| `current_access_m` | Weighted baseline distance over newly covered residents |
| `new_access_m` | Weighted hypothetical distance over the same residents |
| `access_improvement_m` | Positive difference of those means |
| `reason` | Array of strings explaining eligibility and preliminary status |

Contract V1 allows null benefits/distances when unavailable. Accepted candidates
in this stage require measurable positive known-population gain, so all four
benefit/distance fields are numeric. Shared field names and definitions are unchanged.

Optional properties are `source_grid_id`, `nearby_route_ref` (source string or
null), `newly_covered_cells`, `population_quality_notes`, `method_version`,
`unknown_population_cells`, `nearby_route_id` and `route_part_index`. The last
two preserve which source geometry was used even when route labels repeat.

The script follows existing temporary-file, flush/fsync, validate-before-replace
patterns. Only the recommendation output is replaced after validation. No input,
scoring configuration, baseline export or contract is modified. `--verify-only`
recomputes the expected document, reads the existing output and never writes it;
missing output or any mismatch exits nonzero.

Every saved proposal is independently verified using exhaustive distances to all
route parts and all mapped stops, pairwise proposal spacing and a scalar scan of
all grid origins. This verification does not call the indexed selection or
vectorized coverage helper. It checks source eligibility, strict boundary inclusion,
nearest route/tie choice, projection, stable IDs, Contract V1 field types and bounds,
known/unknown/partial population counts, both weighted means and their difference.
Complete-document comparison additionally checks deterministic ranking, omissions,
statistics and input hashes. GeoPandas reload checks EPSG:4326, Point geometry,
counts and IDs. Empty results are valid only when recomputation also finds none;
the script prints screening reasons and never fabricates proposals.

## Initial local result

The inspected baseline inputs produced:

| Screening stage | Count |
| --- | ---: |
| Eligible seeds | 416 |
| Rejected: seed-to-route distance >300 m | 156 |
| Rejected: outside Baku | 0 |
| Rejected: mapped existing stop <300 m away | 0 |
| Rejected: zero known-population coverage gain | 0 |
| Qualified before deduplication | 260 |
| Suppressed within 700 m of a better retained candidate | 195 |
| Retained but beyond the cap | 45 |
| Final recommendations | 20 |

Rejection counts are sequential: each seed is counted at its first failing screen.
The 20 final proposals passed independent verification. These counts describe
this input snapshot, not a guarantee about future data.

## Interpretation limits and next assessment

- **Straight-line, not walking-network distance.** The model cannot establish safe
  pedestrian access, crossing availability, gradients or accessible paths.
- **Incomplete OSM bus-stop coverage.** Apparent gaps may include unmapped stops;
  mapped stops do not establish current operation or service quality.
- **Route geometry does not prove permission or feasibility to establish a stop.**
  Geometry may be stale, imprecise or unsuitable for stopping. Proximity does not
  prove verified stop-route membership, bus frequency or useful service.
- **Field/engineering assessment is required.** Confirm existing stops and route
  operation, suitable carriageway side, stopping space, sight lines, crossings,
  pedestrian accessibility, ownership/permissions, spacing along the route,
  safety and operational effects before any implementation decision.
- Population is modeled with missing and partial coverage. No unknown residents,
  stop boardings, stop-level demand or unique passenger benefits are invented.

## Execution and verification

From the repository root, using the existing environment; no installation needed:

```bash
.venv/bin/python scripts/14_recommend_bus_stops.py
.venv/bin/python scripts/14_recommend_bus_stops.py --verify-only
.venv/bin/python -m unittest discover -s tests -v
```

The synthetic tests cover weighted coverage, null/zero population, non-seed
contributions, cutoffs, multi-part/tied routes, rejection paths, greedy ranking,
stable IDs, the cap and saved-output tampering/read-only verification.
