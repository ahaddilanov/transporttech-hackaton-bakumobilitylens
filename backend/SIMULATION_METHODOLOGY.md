# Standalone accessibility simulations — Step 17A

Model version: `baku-accessibility-simulation-v1.0`.

These are hypothetical **straight-line accessibility estimates**, not predicted
ridership, network journey times, safety assessments or engineering-validated
infrastructure outcomes. Each scenario adds exactly one supplied recommendation
to the unchanged baseline. Scenarios can overlap: **never add their individual
population gains to claim a combined citywide gain**.

## Inputs and measurement geometry

The engine reads each of these local GeoJSON files once per execution:

| Input under `data/processed/` | Inspected contents | Fields used |
| --- | --- | --- |
| `grid/baku_grid_scored.geojson` | 35,029 cells: 35,028 Polygon, 1 MultiPolygon | `id`, `population`, `nearest_bus_stop_m`, `nearest_cycleway_m`, geometry |
| `recommendations/bus_recommendations.geojson` | 20 Points | `id`, `population_affected`, optional known/unknown newly-covered counts and method version, geometry |
| `recommendations/bike_recommendations.geojson` | 14 corridors: 13 LineStrings, 1 MultiLineString | `id`, `population_coverage_gain`, optional known/unknown newly-covered counts, `existing_osm_coverage_excluded_cells`, method version, geometry |

Inputs are EPSG:4326 longitude/latitude; absent GeoJSON CRS means WGS84. Explicit
non-WGS84 CRS, invalid/empty/nonfinite/3D geometry, duplicate IDs, negative or
non-numeric population and unavailable/nonfinite/negative baselines fail explicitly.
The current grid has no missing bus or bicycle baselines. If baselines become
unavailable, this version stops instead of silently changing the denominator or
inventing before distances. Population nulls remain valid unknown observations.
Empty recommendation layers produce no scenarios for that type; no interventions
are invented. The grid must be nonempty.

Project the entire cell polygons and intervention geometry into **EPSG:32639**,
then take each cell's interior `representative_point()` (`point_on_surface`),
matching baseline and recommendation processing. Do not take centroids or measure
meters in longitude/latitude. Each resident modeled in a cell is represented by
that cell origin; subcell population distribution is not modeled.

Bus distance is to the supplied Point. Bicycle distance is to **every part of the
complete exported proposed corridor**, including interior line segments. For
MultiLineStrings, use the nearest actual part; do not connect gaps with new lines.
The bicycle recommendation output already omits existing infrastructure segments.
Its full routed `route_edges` trace is not substituted for its exported new geometry.

SHA-256 hashes, feature counts and observed fields are stored in output provenance.
When a recommendation records its source grid hash, it must match the loaded grid.
The simulator needs no graph, raw infrastructure layers, routing service or network
request. The separate read-only source investigation below does not add a runtime
dependency on the graph.

## Exact formulas and numerical tolerance

For each grid cell `i` and one intervention, let:

```text
p_i = modeled population, or null
b_i = nearest_bus_stop_m for bus_stop
      nearest_cycleway_m for bike_corridor (mapped AYNA-lane baseline)
d_i = EPSG:32639 distance from the cell origin to the intervention geometry
a_i = min(b_i, d_i)
r_i = b_i - a_i
K   = cells with known population (including observed zero)
P   = sum(p_i for i in K)
I   = cells where r_i > 0.000001 meters
N   = cells where b_i > 500 meters and a_i <= 500 meters
```

The **absolute improvement tolerance is 1e-6 m**; equality does not count as an
improvement. It suppresses projection/floating-point noise, not meaningful access
change. Coverage uses the exact inclusive 500 m cutoff without a tolerance buffer:
baseline exactly 500 m is already covered, and after exactly 500 m is covered.
A reduction smaller than the improvement tolerance can exceptionally cross 500 m;
such a cell counts as newly covered but not distance-improved. These two tests
remain separate rather than silently altering the coverage definition.

The required Shared Contract V1 fields are computed as follows:

| Field | Definition |
| --- | --- |
| `intervention_id` | Exact recommendation `id`, unchanged; no new rank-dependent ID |
| `intervention_type` | `bus_stop` or `bike_corridor` |
| `population_improved` | `sum(p_i for i in K intersect I)` |
| `affected_cells` | Number of cells in `K intersect I`, including known zeros |
| `coverage_before_pct` | `100 * sum(p_i for i in K where b_i <= 500) / P` |
| `coverage_after_pct` | `100 * sum(p_i for i in K where a_i <= 500) / P` |
| `coverage_change_pp` | `coverage_after_pct - coverage_before_pct`, in percentage points |
| `avg_access_improvement_m` | `sum(p_i*r_i for i in K intersect I where p_i>0) / sum(p_i for i in K intersect I where p_i>0)` |

Both coverage percentages use the **same full-grid known-population denominator**,
not intervention-local population, target cells, the study area, only improved
residents, or counts of cells. For example, 20% before and 80% after is **60
percentage points**, not 300% relative growth.

Improvement includes residents who were already covered and those who remain
outside 500 m. There is no arbitrary maximum improvement radius. Consequently,
`population_improved` can greatly exceed newly covered population, especially
for cycling when the existing AYNA baseline is far away. It is a proximity
comparison, not evidence that those residents would use the corridor or could
reach it through the street network.

Additional fields:

- `newly_covered_population`: known population in `N`.
- `newly_covered_cells`: known-population cells in `N`, including known zeros.
- `unknown_population_cells_affected`: null-population cells in `I`.
- `unknown_population_cells_newly_covered`: null-population cells in `N`.
- `model_version`, `coverage_radius_m` and a structured `reconciliation` record.

All weighted sums use `math.fsum`, with cells sorted by stable ID. Values are
unrounded JSON numbers, including fractional modeled residents. Numerical checks
allow `abs_tol=1e-8`, `rel_tol=1e-12` for independently calculated values; complete
saved-document equality is also required against deterministic regeneration.

## Missing population, zeros and undefined means

Unknown cells never enter population sums, weighted means or coverage denominators.
They are counted separately, not assigned zero residents. Known partial-raster
population is used as supplied, without extrapolation or changes to priority.

- If there are known-population cells but none benefit, population sums and
  counts are **0**, while average improvement is **null** (no positively weighted
  improved residents).
- Known zero-population cells count as affected/newly covered when geometrically
  eligible but have no population weight.
- If the entire grid's population is unknown, population sums are **null**, known
  affected/newly covered counts are **0**, and unknown counts remain observable.
- If total known population is zero, coverage percentages and their change are
  **null** because the denominator is zero. This includes an entirely unknown
  grid and a grid with observed zeros only. With observed zeros, population sums
  remain numeric **0**.
- A null recommendation benefit produces reconciliation status `unavailable`;
  it does not erase independently calculable simulation values.

## Reconciliation and the bicycle policy difference

Bus recommendation `population_affected` describes **newly covered** population,
not all distance-improved residents. Compare it with `newly_covered_population`,
not `population_improved`. Check its optional known/unknown newly-covered cell
counts too. An unexplained discrepancy fails before replacement of output.

Bicycle recommendation `population_coverage_gain` applies the AYNA-baseline
500 m test **plus** a separate condition: the cell must be more than 500 m from
classified existing OSM bicycle infrastructure. See
[BIKE_RECOMMENDATIONS_METHODOLOGY.md](BIKE_RECOMMENDATIONS_METHODOLOGY.md).
The requested simulation uses the AYNA-only baseline and supplied new corridor.
It therefore intentionally does **not** apply that additional OSM condition, alter
the baseline, or overwrite recommendation benefits.

Each reconciliation records the recommendation value, simulation value and signed
population difference. Status is:

- `match`: population and available known/unknown newly-covered counts agree.
- `unavailable`: either population total is null.
- `consistent_with_osm_exclusion`: the recognized `baku-bike-corridors-v1.0`
  method reports positive OSM exclusions; simulation population is no smaller;
  both known and unknown cell differences are nonnegative and their sum equals
  the recorded exclusion count. Count-only differences with zero population
  difference are also possible when excluded cells have zero/unknown population.
- Any other discrepancy raises an error, rather than being silently ignored.

The three simulator inputs do not identify exactly which cells the OSM gate
excluded. Therefore `osm_gate_recomputed_by_simulator=false` accompanies policy
differences: aggregate consistency alone cannot verify the excluded population
cell by cell. Verification independently recalculates **every simulation value**,
but does not claim to repeat the graph-based OSM audit.

### Source investigation for the current snapshot

All **20 bus** gains match exactly. **9 bicycle** gains match exactly; the other
**5 differences** were investigated by loading the existing saved graph read-only,
classifying existing cycling segments with the existing recommendation module's
`classify_existing(raw_tags(edge))`, unioning those EPSG:32639 geometries, and
measuring every AYNA-newly-covered cell's distance to that union. The graph was
neither rebuilt nor downloaded. All 14 gated population sums and all exclusion
counts reproduce the existing recommendation values exactly.

Source hashes for that audit:

```text
grid: b4adbeea06340b5228cb4ede3f3288304d74d9de6101f1e603c2e6b0df44e00a
bike recommendations: 17057804718463f59a123ef22d579127e9fcff4461430e4a0df2f80e789f1540
graph: 99cdb83651feb38742b79046e65aa989263dcc6669d5226a9f36a34ec235b033
```

Full IDs are `baku:bike-corridor:` followed by the digest below:

| Digest | Recommendation gain | AYNA-only simulation gain | Difference | OSM-excluded known cells |
| --- | ---: | ---: | ---: | ---: |
| `744e944bda543015e55a0295f5d98a33891c0b58c852fcb71e576c550e55688f` | 44,775.777861 | 46,853.528655 | 2,077.750793 | 3 |
| `0f75c7221217dd142a9d4cbcb9e4d29a136400d1c70772550b4967f418719b98` | 29,612.662590 | 31,690.413383 | 2,077.750793 | 3 |
| `9374713797c22be91e9d5863f69fc1737cdd80eca0a4ab66cf272a5f4b8b89c2` | 15,586.935178 | 16,151.462082 | 564.526904 | 2 |
| `5ac1bddb29012f9063701bbdc0f2811a338594468b252e836bab103b82e33330` | 16,499.905532 | 17,064.432436 | 564.526904 | 2 |
| `13732b67bd59c1f16530071e251d1286a31a039bd79252d27078c7283d9b8e7c` | 15,473.032955 | 24,991.703134 | 9,518.670178 | 15 |

For the first two, excluded grid IDs share prefix `baku:250m:` and are
`r17874:c1644`, `r17875:c1644`, `r17875:c1645`, with respective population
918.765686, 704.369591, 454.615517 and OSM distances 155.015, 402.065, 451.437 m.
The next two exclude `r17869:c1601` and `r17870:c1601`, with population
221.069661 and 343.457243 and distances 464.663 and 407.032 m.
The last excludes `r17870:c1645`, `r17871:c1644` through `r17874:c1646`
(all three columns 1644–1646 in each of those four rows), and
`r17875:c1644`, `r17875:c1645`. Their OSM distances range from 13.089 to 451.437 m.
All excluded cells in this snapshot have known population. Several exclusion
sets overlap; the differences in this table must not be added as unique residents.

## Output, determinism and verification

`data/processed/scenarios/intervention_scenarios.json` contains:

```text
metadata: model, metric CRS, coverage/tolerance, source hashes, population denominator, limitations
summary: per-type scenario counts, reconciliation counts, per-scenario min/max ranges
scenarios: array of Contract V1 simulation records and optional explanatory fields
```

Records sort by `(intervention_type, intervention_id)`. IDs are the exact stable
recommendation IDs. No timestamp, random value or input feature order enters the
calculations. Identical inputs and installed geometry stack produce identical
output bytes. Reordering grid/intervention features preserves scenario values and
IDs; source byte hashes legitimately change if source files are reordered.

NumPy/Shapely vectorized distances scan all 35,029 origins per intervention: only
about 1.19 million distances for 34 scenarios. Full line geometries are used.
A 500 m spatial prefilter would incorrectly omit improvements beyond the coverage
threshold; none is applied. There are no routing searches or repeated GeoJSON
reads. Independent verification deliberately uses a separate scalar loop over
all cells, reading original cell properties and calling scalar geometry distance;
it does not reuse the vectorized masks, population arrays or cached denominator.

Every result is independently recomputed, with field types, IDs, counts,
population weighting, coverage bounds, nondecreasing coverage, reconciliation,
summary and provenance checked. Temporary output is reloaded and verified before
atomic replacement; failed verification preserves any prior output. `--verify-only`
only reads and calculates, and fails if saved output is missing or stale.

Synthetic tests independently specify numeric expectations, percentage points,
known zeros, unknown populations, undefined means, no benefit, exact coverage
cutoffs and improvement tolerance, full line/MultiLineString distances and gaps,
reconciliation differences, metric projection, malformed inputs, stale grid
hashes, empty recommendations, stable IDs/repeatability, one read per input,
tamper detection, offline operation, query behavior and read-only verification.

## Snapshot summary and examples

There are **34 standalone scenarios: 20 bus stops and 14 bicycle corridors**.
The common denominator is **2,898,185.146992981** modeled residents across **19,112**
known-population cells; **15,917** cells have unknown population.

| Type | Baseline coverage | Per-scenario newly covered population range | Per-scenario coverage change range |
| --- | ---: | ---: | ---: |
| Bus stop | 57.442166% | 4,128.20–10,209.49 | +0.142441–+0.352272 pp |
| Bike corridor | 14.485987% | 16,151.46–68,841.87 | +0.557296–+2.375344 pp |

Examples, each measured independently:

| Scenario ID suffix | Population improved | Newly covered population | Before → after coverage | Mean improvement among improved residents | Known affected cells |
| --- | ---: | ---: | --- | ---: | ---: |
| Bus `07da2e8eceec8e3f60350cc37a864e149dc68d15709249d0f3138f6e4fb88333` | 19,519.80 | 10,209.49 | 57.442166% → 57.794438% | 391.94 m | 30 |
| Bike `15c4a81baf78dd0bf22686c2e752adbff3d7e9c4d5d1225205b5cd1ba10cb417` | 770,955.99 | 68,841.87 | 14.485987% → 16.861331% | 1,550.29 m | 3,276 |

The bike example also improves geometric distance for 1,630 unknown-population
cells; none enters its population totals. Its large improved population includes
many residents still outside 500 m. These estimates do not demonstrate demand,
safe access, connectivity, approval, construction feasibility or operational service.

## Commands

From `/home/osman/projects/transporttech-backend`, using existing dependencies:

```bash
.venv/bin/python scripts/17_simulate_accessibility.py
.venv/bin/python scripts/17_simulate_accessibility.py --verify-only
.venv/bin/python -m unittest discover -s tests -v

.venv/bin/python scripts/17_simulate_accessibility.py \
  --intervention-id baku:bus-stop-recommendation:07da2e8eceec8e3f60350cc37a864e149dc68d15709249d0f3138f6e4fb88333

.venv/bin/python scripts/17_simulate_accessibility.py --verify-only \
  --intervention-id baku:bike-corridor:15c4a81baf78dd0bf22686c2e752adbff3d7e9c4d5d1225205b5cd1ba10cb417
```

An ID query alone computes/verifies just that intervention from current inputs
without writing, even if saved scenarios do not exist. Combining it with
`--verify-only` verifies the entire saved document before returning the selected
scenario. Unknown IDs fail nonzero. Query stdout contains only the selected JSON
record; schemas, summaries and diagnostics go to stderr. Normal generation and
verification print counts, ranges, reconciliation checks and one example of each
type. No graph/network access, dependency installation or commit occurs.
