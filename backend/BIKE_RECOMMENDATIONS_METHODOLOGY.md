# Preliminary bicycle corridors — Step 16B-2

Method: `baku-bike-corridors-v1.0`. These are **investigation candidates**, not
construction-ready designs, safe routes, approved projects or verified legal access.
No original dataset, scoring model, frontend file or Shared Contract V1 is changed.

## Inspected sources and coordinate systems

| Existing input under `data/processed/` | Observed schema/use |
| --- | --- |
| `networks/baku_bike.graphml` | OSMnx 2.1.1 directed MultiDiGraph, **EPSG:32639**, 80,957 nodes and 155,944 original directed OSM way segments; each edge has oriented LineString geometry, `osmid`, `length`, `length_utm_m`, normalized boolean `oneway`, `reversed`, and original `osm_tags_json` |
| `networks/baku_bike_study_area.geojson` | One EPSG:4326 Polygon, 110.244005715 km²; metadata includes the validated GraphML hash and counts |
| `transport/cycleways.geojson` | 60 EPSG:4326 AYNA LineStrings: `id`, `name`, `length_m`, `source` |
| `grid/baku_grid_scored.geojson` | 35,029 EPSG:4326 Polygon/MultiPolygon cells; `id`, `population`, `bike_priority`, `nearest_cycleway_m`, `valid_pixel_fraction`, `scoring_model_version` |
| `pois/essential_services.geojson` | 1,751 EPSG:4326 Points; actual fields include `id`, `name`, `category`, `TYPE`, `status`, `source`, `validation_flags` |

The graph also contains bicycle/access/oneway variants, cycleway-side tags,
surface, maxspeed, service, bridge, tunnel, lighting and barrier context. Some
fields are missing on most edges. Original tags are used rather than assuming
the graph's `bike` filter has verified cycling legality or safety. Its default
directionality does not fully implement bicycle contraflow or turn restrictions.

All geometric work is in **EPSG:32639**. Grid measurement origins are interior
representative points after projection, matching the baseline scripts. The saved
graph is loaded locally; it is never rebuilt, redownloaded or modified. All other
source layers are projected in memory. Export uses EPSG:4326 `[longitude, latitude]`
LineString/MultiLineString geometries. Distances and physical lengths are meters.

Input schemas, bounds and geometry are checked; output metadata records all five
SHA-256 hashes. Graph hash/counts must match the saved study metadata. Stored
`nearest_cycleway_m` must reproduce distance to the current AYNA lines within
0.000001 m. Missing/invalid/stale inputs fail rather than silently changing the model.

## Targets, AYNA associations and useful destinations

- Target every cell whose representative point is strictly inside the study area,
  with known population and `bike_priority >= 60`. Unknown-population scores are
  not invented. Known zero population is allowed as a target but cannot supply
  positive resident benefit by itself. The current snapshot has **255 targets**.
- An AYNA connection candidate is an actual eligible graph node within **25 m**
  of any AYNA line and with an eligible outgoing edge. Associate it with the
  nearest complete AYNA geometry; exact ties use ascending AYNA source ID. All
  such nodes are considered, including those in disconnected components.
  The current snapshot has **4,212 proximity anchors**.
- `anchor_snap_m` records node-to-AYNA distance; the route begins at that graph
  node. This is an approximate geometric association, **not verified physical
  connection**. No straight line is added between the AYNA lane and the node.
  Even a small offset may cross a barrier or carriageway and needs field checks.
- Search for useful POIs within **500 m** of each target origin, inside the study
  polygon. Use the actual `category`, with deterministic preference order
  `HOSPITAL`, `SCHOOL`, `KINDERGARTEN`, `PHARMACY`, then origin-to-POI distance,
  then POI ID. `CUSTOMIZABLE_POINT_5` is excluded as an ambiguous mixed category.
- Choose the first POI in that order whose nearest eligible graph node is within
  **100 m** of the POI and **500 m** of the target origin. If none qualifies, use
  the target origin's nearest eligible node, with maximum snap **150 m**.
  Exact node-distance ties use ascending OSM node ID. Neither target nor POI
  snaps introduce off-network geometry or prove an accessible entrance.
- POI selection precedes route feasibility checks. An unreachable chosen endpoint
  fails; the algorithm does not try progressively different endpoints or sources
  until something passes. A POI-free target has `end_name=null`.

Source POI categories/names do not prove operating status, public access or a
verified facility type. In particular, `HOSPITAL` includes dental/medical/military
clinics in the supplied data. Named destinations receive the flag
`destination_status_and_public_access_unverified`; no public hospital or verified
university claim is made. POI preference is a planning assumption, not estimated demand.

## Conservative routing eligibility

Create a filtered **in-memory** directed routing view. It never adds nodes,
reverses an edge or bridges missing links in the saved graph. Eligibility uses
lowercase trimmed original tag values; names in output retain their source spelling.

Reject:

1. Highway types outside the cost table below. This excludes **trunk and
   trunk_link everywhere**, including existing cycling segments on them.
2. Any explicit general `bicycle` value other than `yes`, `designated`,
   `permissive` or `official`, including `no`, `dismount` and `use_sidepath`.
3. `access` equal to `no`, `private`, `customers`, `destination`, `delivery`,
   `permit`, `agricultural`, `forestry` or `military`. This conservative rule
   also excludes a restricted access tag accompanied by an explicit bicycle tag.
4. Any `access*`, `bicycle*` or `oneway*` tag containing `:conditional`;
   schedules/conditions are not interpreted.
5. Busways, paths, tracks or pedestrian ways lacking one of the explicit allowed
   bicycle values. A busway is only supported by explicit bicycle permission;
   it still carries an operational-assessment risk flag.
6. Service purposes `parking_aisle`, `driveway`, `emergency_access` or `private`.
7. A directed edge whose matching `bicycle:forward`/`bicycle:backward` value is
   explicit and outside the allowed bicycle values. Direction relative to the
   original OSM way uses `reversed XOR (original oneway is -1/reverse)`.
8. Bicycle-specific oneway `yes/1/true` in the original backward direction,
   or `-1/reverse` in the original forward direction. General or bicycle oneway
   values outside absent/yes/1/true/no/0/false/-1/reverse are unsupported and rejected.
9. A parsed maximum speed **greater than 60 km/h**. Numeric, `km/h`, `kph` and
   `mph` values are recognized; semicolon lists use the maximum. Other values
   are unknown and penalized where road-speed information is relevant.

Nodes with `access` or `bicycle` in the restricted-access list are excluded.
Missing/no barriers and `bollard`, `entrance`, `kerb` are allowed with review;
other barriers require an explicit allowed bicycle tag on that node. Any populated
barrier tag on an edge endpoint adds the surcharge below. These rules cannot
establish actual barrier passability or accessible crossings.

Travel always follows saved directed edges. `oneway:bicycle=no` on a one-way
street does **not** cause a new reverse edge: the potentially missing contraflow
is flagged. Per-side lane direction tags do not authorize reversing the centerline
graph. Missing turn-restriction relations and conditional rules remain limitations.

## Routing cost, intervention priority and physical safety

The cost is a transparent planning preference, **not a safety score**, travel time,
crash probability, construction cost or proof of a suitable road cross section.
For each eligible edge, `cost = EPSG:32639 geometry length * factor`.

| Highway type | Initial factor |
| --- | ---: |
| cycleway | 1.0 |
| living_street | 1.2 |
| residential | 1.5 |
| path / pedestrian / track | 1.6 / 1.8 / 2.0 |
| unclassified / service | 2.5 / 2.8 |
| tertiary / tertiary_link | 3.0 / 3.3 |
| secondary / secondary_link | 4.0 / 4.3 |
| primary / primary_link / supported busway | 5.0 / 5.3 / 5.0 |

For edges classified as mapped existing cycling infrastructure below, cap this
initial factor at **1.2**. Then add all applicable surcharges:

| Tag condition | Added factor |
| --- | ---: |
| Missing surface | 0.50 |
| Surface gravel/fine_gravel/ground/dirt/earth/unpaved/sett/cobblestone/sand/mud | 1.00 |
| Other surface outside asphalt/paved/concrete/paving_stones/concrete:plates | 0.75 |
| Unknown maxspeed on a road other than cycleway/path/track/pedestrian | 0.75 |
| Speed >30 and <=50 km/h on those roads | 1.00 |
| Speed >50 and <=60 km/h on those roads | 2.50 |
| Lighting not explicitly `yes` | 0.25 |
| Missing bicycle tag except highway=cycleway | 0.25 |
| Service road with service=alley / any other retained service subtype or missing subtype | 0.50 / 1.00 |
| bridge or tunnel tag present and not no/false/0, separately per tag | 0.75 each |
| Any populated barrier tag at either endpoint | 0.50 once per edge |

Risk flags disclose these uncertainties and traversed existing OSM infrastructure.
Inclines, traffic volumes, turn restrictions, available width and crossing safety
are not converted into invented safety estimates; field/engineering assessment is
required even when a route has lower cost.

For parallel eligible edges in the same direction, retain minimum `(cost, edge key)`.
Sort edge insertion and AYNA source nodes by their stable OSM IDs. Run **one**
NetworkX multi-source Dijkstra search for all targets, following the
[documented API](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.shortest_paths.weighted.multi_source_dijkstra.html).
Its cost cutoff is `4000 * maximum retained edge factor`, which contains the
cost of every possible route of physical length <=4000 m. There are no repeated
all-node searches per target or source. Geometry/node/grid/POI STRtrees support
snapping and coverage. Each target gets one minimum-cost directed path; a longer
minimum-cost route is rejected rather than searching for alternative feasible paths.

Contract V1 `priority` remains the target cell's **unchanged `bike_priority`**,
0–100, measuring local intervention need. Routing suitability is the separate
dimensionless `network_distance_m / routing_cost`, in (0,1]. Neither implies safety.

## Existing infrastructure, exported geometry and length

Treat an OSM edge as mapped existing bicycle infrastructure when:

- `highway=cycleway`; or `highway=path/track` and `bicycle=designated`; or
- any `cycleway`, `cycleway:left`, `cycleway:right`, `cycleway:both` equals
  `lane`, `track`, `opposite`, `opposite_lane`, `opposite_track`, `shared_lane` or `separate`.

The last two values conservatively prevent new-construction claims on an already
described cycling corridor. `bicycle=yes` alone, crossings, shoulders and shared
busways/sidewalks do not establish a constructed bicycle lane.

Build an existing-infrastructure exclusion mask from **25 m buffers around all
AYNA lanes** and **10 m buffers around all classified existing OSM segments**,
including mapped segments not retained by the routing eligibility model. Buffers
are explicit positional-association tolerances, not verified lane widths. Subtract
this mask from the full directed route. Export only the remaining new portions.
This may yield disconnected MultiLineString pieces linked through existing
infrastructure in the complete graph trace. It does not invent connections between
the new pieces. Ordered `route_edges` identifies the complete continuous source
trace and allows existing connecting segments to be inspected separately.

Require **new proposed length >=200 m** and **full network trace <=4000 m**.
Both thresholds are inclusive. `length_m` and `new_corridor_length_m` equal the
complete exported NEW geometry length; `network_distance_m` is the full routed
trace; `existing_connection_length_m` is their difference. The excluded portion
includes registration buffers, so it is not a surveyed inventory of lane length.
Coverage/length use the exact exported geometry after a WGS84-to-UTM roundtrip.

## Population and accessibility benefit

Evaluate all grid origins, including non-target cells and cells outside the study
area if they lie within 500 m of the proposal. Never use just an endpoint.

```text
b_i = unchanged nearest_cycleway_m (distance to mapped AYNA lanes)
d_i = straight-line distance to the COMPLETE proposed NEW geometry
a_i = min(b_i, d_i)
o_i = distance to any classified existing OSM bicycle-infrastructure segment
```

The AYNA-baseline newly covered test is **`b_i > 500 and a_i <= 500`**. Add the
conservative gate **`o_i > 500`** so residents already near known OSM infrastructure
are not claimed as newly served. If none is mapped, `o_i` is effectively infinite.
This separate existing-OSM gate does **not** overwrite the AYNA baseline or scores;
it makes reported gain a conservative subset of the pure AYNA-baseline change.
`existing_osm_coverage_excluded_cells` reports excluded cells separately.

`population_coverage_gain` is the sum of modeled population in qualifying cells
with non-null population. `newly_covered_cells` includes qualifying known zeros;
`unknown_population_cells` separately counts qualifying null-population cells.
`partial_population_cells` counts known qualifying cells with valid-pixel fraction
below 1. No missing population is filled, extrapolated or counted as zero.
Zero known-population gain is rejected. Optional `current_access_m` and
`new_access_m` are population-weighted means of `b_i` and `a_i` over these newly
covered known residents; `access_improvement_m` is their positive difference.

All coverage is **straight-line, not walking/cycling-network access**, and uses
modeled WorldPop residents rather than trips, ridership or an official census.
Missing AYNA/OSM infrastructure can overstate apparent unmet need. Benefits are
standalone against the same baseline; **do not sum proposals into a combined
citywide population gain**. Coverage footprints can overlap after corridor deduplication.

## Ranking, overlap and IDs

Use the exact, unrounded planning formula:

```text
ranking_score = population_coverage_gain
                * (0.5 + 0.5 * priority / 100)
                * routing_suitability
```

Sort ascending by `(-ranking_score, -population_coverage_gain, -priority,
-routing_suitability, source_grid_id, id)`. The priority weight/factors are
explicit assumptions, not calibrated empirical weights or modifications to baseline v1.

Greedily retain a candidate unless either direction of the following overlap
test reaches **60%**: fraction of its new geometry lying within a **20 m buffer**
of a previously retained new geometry. This also suppresses a corridor largely
contained in a longer alternative and opposite-direction copies. It is a
geographic similarity rule, not a link added to the graph. Process all candidates
for duplicate statistics, then select the first **at most 15** retained proposals.
Rejected candidates do not suppress others. Never fill remaining slots artificially.

IDs are `baku:bike-corridor:` plus full SHA-256 of compact sorted-key UTF-8 JSON:
`[method_version, source_grid_id, source_cycleway_id, destination_id, route_edges,
normalized_new_metric_geometry_WKT_at_6_decimal_places]`. Rank/array position
is excluded. Identical inputs and method reproduce output and IDs; source-grid
reordering does not change results. Source graph/geometry/path/method changes
may change IDs. These are project IDs, not official infrastructure identifiers.

## Output, verification and initial result

The EPSG:4326 FeatureCollection at
`data/processed/recommendations/bike_recommendations.geojson` contains all required
Contract V1 fields: string `id`; numeric 0–100 `priority`; numeric `length_m` and
`population_coverage_gain`; source-backed string/null `start_name` and `end_name`;
and string-array `reason`. Accepted proposals have known positive benefits, so
the contract's nullable length/benefit fields are numeric in this stage.

Optional fields include `source_grid_id`, `network_distance_m`,
`new_corridor_length_m`, `routing_risk_flags`, `newly_covered_cells`,
`unknown_population_cells`, `scoring_model_version`, `method_version`, source
AYNA/destination IDs, actual anchor/target node IDs and snap distances, ordered
`route_edges`, existing-connection length, cost, suitability, rank, weighted access
distances, partial-population and existing-OSM exclusion counts. A MultiLineString
represents new portions, not a claim that all its gaps are new construction.

Every saved proposal is checked for Contract V1 field types, score bounds, source
IDs, eligibility, directed edge-by-edge continuity, source geometry endpoints,
AYNA/target snaps, new-versus-existing geometry, physical lengths, cost, risk flags,
stable IDs and overlap. Independently recompute each population gain and both
weighted access means by scanning all grid origins using scalar geometry distances
and the existing OSM geometry union: no production coverage helper, grid spatial
index or cached existing-OSM distances are reused. Complete-document comparison
also checks deterministic candidate selection, statistics and provenance. Reload
checks EPSG:4326 and line geometry. Temporary output is verified before atomic
replacement; failures preserve any previous valid recommendation file.

Initial snapshot: **255 eligible targets**, **36 routing failures**, **0 target
access/snap rejections**, **90 length rejections**, **0 zero-gain rejections**,
**115 overlapping alternatives removed**, **14 final distinct proposals**. Edge
eligibility rejections are reported separately; target counts are sequential.
Fourteen is the measured outcome under fixed rules, not a quota to reach fifteen.
The five highest-ranked standalone modeled-population gains are approximately
**68,841.87; 33,407.36; 44,922.09; 44,775.78; 37,932.57**; their order also reflects
local priority and routing suitability. They are not additive unique residents.

Run from the integrated repository's `backend/` directory with the existing environment:

```bash
.venv/bin/python scripts/16_recommend_bike_corridors.py
.venv/bin/python scripts/16_recommend_bike_corridors.py --verify-only
.venv/bin/python -m unittest discover -s tests -v
```

`--verify-only` loads saved inputs/output, recomputes expected proposals and
validates without writing or requesting any network service. Missing output or
any mismatch exits nonzero. No network download path exists in this script.
If none qualify, the script reports screening reasons and writes/verifies an
honest empty FeatureCollection. It never relaxes thresholds or invents corridors.
