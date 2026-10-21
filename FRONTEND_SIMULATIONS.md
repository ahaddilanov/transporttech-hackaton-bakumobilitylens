# Saved before/after accessibility comparisons

Release setup: `npm test` now runs the source-independent formatting/validation
checks; `npm run test:real-data` retains the complete-snapshot ID and five-policy-
difference assertions formerly embedded in `tests/scenarios.test.mjs`. The real
scenario file is intentionally not shipped. Use `npm run dev:demo` for the separate
synthetic saved comparisons. The implementation and earlier measurements below
describe the real local snapshot.

The existing DetailsPanel now includes a native, initially collapsed **Before / After accessibility** section for bus and bicycle recommendations. It loads `public/data/intervention_scenarios.json` through the existing parallel JSON-loading and validation path. No simulation is calculated in the browser and no additional floating panel is created.

## Inspected data and matching

The actual JSON root is an object with `metadata`, `summary`, and a `scenarios` array. This snapshot contains 34 individual scenarios: 20 `bus_stop` and 14 `bike_corridor` records. The scenario index uses each complete, case-sensitive original `intervention_id`, including its full digest. Selection also checks intervention type; an unrelated feature or a shortened/missing/wrong-type ID cannot match. Ranking order and short display labels are not used as keys.

Validation rejects malformed roots, missing Contract V1 fields, nonfinite/wrong-type numbers, out-of-range coverage, fractional/negative counts, duplicate scenario IDs, unsupported types, inconsistent percentage-point differences and inconsistent reconciliation values. Optional fields and original metadata are retained without mutation. Empty scenario arrays and nullable values are supported. No existing Contract V1 validator is changed.

The saved file remains a static source even if other layers use `VITE_API_BASE_URL`; no new backend API endpoint is assumed. API recommendations with unmatched IDs show an unavailable comparison. The static snapshot must be refreshed through the existing validated backend export workflow when source datasets change.

## Interpretation and presentation

The section displays these saved values, formatted only for presentation:

| Label | Source field | Meaning |
| --- | --- | --- |
| Coverage before | `coverage_before_pct` | Population-weighted baseline coverage within 500 m |
| Coverage after | `coverage_after_pct` | Population-weighted coverage after this one intervention |
| Coverage change | `coverage_change_pp` | After minus before, in percentage points; never relative percent growth |
| Population newly within 500 m | `newly_covered_population` | Known modeled residents crossing the 500 m threshold |
| Population with improved proximity | `population_improved` | Known modeled residents with a distance reduction, including those already covered or remaining outside 500 m |
| Average access improvement | `avg_access_improvement_m` | Population-weighted mean reduction over improved residents |

Coverage uses the same full-grid known-population denominator before and after. Unknown population is excluded rather than treated as zero; affected unknown-population cell counts are shown when present. Zero remains zero. Null or absent optional values show “Unavailable.” Population estimates use whole numbers; distances use rounded metres or kilometres; percentages have one or two decimal places. Changes use `pp` with their own saved, unrounded difference, rather than subtracting rounded display percentages. Tiny nonzero changes below 0.01 pp are labeled explicitly.

Each scenario is hypothetical straight-line accessibility from the unchanged baseline. It is not ridership, a walking/cycling network journey-time estimate, an approval or an engineering assessment. Separate scenario gains can overlap and are never summed in the frontend.

## Bicycle baseline and reconciliation

All bicycle scenarios use the mapped AYNA-lane baseline. Recommendation estimates also exclude cells within 500 m of classified existing OSM cycling infrastructure. Nine bicycle values match; five have saved `consistent_with_osm_exclusion` records. All 20 bus records match their recommendation's newly covered population.

For each of those five bicycle records, the inspector shows both the recorded recommendation estimate and the AYNA-only simulation estimate, the readable reconciliation status, and the saved methodology explanation. The `osm_gate_recomputed_by_simulator=false` limitation is explained: the simulator checked aggregate consistency with recorded exclusions and did not independently determine which cells OSM excluded. No recommendation value, scenario value, reconciliation status or limitation is overwritten. See the unchanged backend/SIMULATION_METHODOLOGY.md for the separate source audit and formulas.

## Loading, failures and rendering

The selected scenario is a constant-time lookup in a memoized 34-entry index. Scenario props go only to DetailsPanel, not to the grid or map layers. Expanding/collapsing the native details element needs no React state change. Browser instrumentation confirmed zero grid `setStyle` calls and zero GeoJSON `addData` calls when delayed scenario loading completed or the comparison was toggled. Existing 35,029 grid objects and the Canvas were retained.

While loading, the section displays a loading message. A missing exact-ID match shows a specific unavailable message. Fetch/validation failures use the existing data-status error handling and leave recommendation/map functionality available. New recommendation selections reset the comparison to collapsed. Native summary controls retain keyboard operation and existing theme/mobile styles.

## Verification

Run from `~/projects/transporttech-integrated`:

```bash
npm run lint
npm run build
node tests/scenarios.test.mjs
node tests/presentation.test.mjs
node tests/bounds-index.test.mjs
```

For the browser checks, start the local Vite server and an isolated Chrome profile using the commands in FRONTEND_PERFORMANCE.md, then run sequentially:

```bash
node tests/simulation-browser-check.mjs
node tests/map-browser-check.mjs
```

The new seven-test suite validates the actual 34 matches, all five policy differences, schema rejection, full-ID/type matching, percentage-point interpretation, formatting, null/zero behavior and non-mutation. Together with the six existing pure tests, all 13 pass.

The new browser suite holds then releases scenario responses to verify loading and grid stability. It checks actual bus and bicycle values, reconciliation notes/status, keyboard collapsing, dark/mobile presentation, and intercepted empty/null/zero/404/duplicate fixtures without modifying files. The existing map browser suite also passes with actual scenario loading, covering feature clicks, grid identity/colors, no hover effects, drag/zoom, selection clearing, ranking/keyboard controls, themes/mobile and null/empty states. Both suites completed without unhandled runtime exceptions; error fixtures intentionally exercise the existing load-error reporting. OSM tiles are blocked during these tests. Physical touch devices and live tile loading are not tested.

SHA-256 checks of the 78 protected backend/public-data files confirm they are unchanged. No dependency was added and no commit or push was made.

## Changed files

- `src/App.jsx`: scenario loading, memoized index and selected-scenario props.
- `src/data/dataSources.js`, `src/data/validateData.js`: new static source and validator export.
- New `src/data/validateScenarios.js` and `src/data/scenarios.js`: schema checks and exact-ID/type lookup.
- `src/components/DetailsPanel.jsx`: embeds the comparison only for recommendations.
- New `src/components/BeforeAfterComparison.jsx` and `.css`: comparison, explanations, loading/empty states, responsive theme-aware styling.
- `src/utils/presentation.js`: percentage and percentage-point display helpers.
- New `tests/scenarios.test.mjs` and `tests/simulation-browser-check.mjs`.
- This report and a corrected simulation-UI reference in `FRONTEND_PERFORMANCE.md`.

PriorityRanking, map/rendering components, existing recommendation/score behavior, package manifests and backend files are unchanged. Existing working-tree changes under `public/data/` predate this task and were preserved.
