# Frontend rendering and readability

Implemented against the local `integration/backend-and-scenarios` workspace and its complete Baku datasets. No backend, Shared Contract V1, processed/exported/public dataset, score, or simulation changes are required.

## Rendering decisions

- `GridLayer.jsx` creates Leaflet geometry once per dataset. Metric changes call `setStyle`; they do not use `key={selectedMetric}`, recreate GeoJSON, or replace the Canvas. Hiding/showing the grid reuses the same feature objects.
- Only the 35,029-cell grid uses Canvas. The smaller transport layers retain SVG, existing hover/selection behavior, CSS styling, and keyboard interaction. A memoized transport-layer component avoids unrelated styling work when the grid metric changes.
- Four handlers on the GeoJSON group provide grid click/hover behavior through Leaflet event propagation. A single tooltip creates content only when a cell is hovered. There are no application tooltip objects, keyboard handlers, or SVG elements allocated per grid cell. Leaflet still maintains its own feature objects and internal event relationships.
- Canvas feature clicks stop propagation; empty Canvas clicks clear selection. The separate SVG selection halo remains visible above the grid.
- Canvas has no focusable element per cell. Skip links lead directly to analysis controls and recommendations. The analysis cell browser searches every cell by ID, displays ten at a time, and supports keyboard selection, pagination, map focus, and the existing inspector. Existing transport SVG features remain keyboard-accessible.

## Presentation decisions

- Population/count estimates display whole numbers. Distances below 1,000 m display rounded metres; distances at or above 1,000 m display kilometres with up to two decimals. Zero remains zero; null/undefined remain “Unavailable.” Values are formatted without changing the underlying properties.
- Known reason codes map to sentences; unknown reasons retain their original text. Raw reason arrays remain intact.
- Recommendation labels use source-dataset order: `Candidate Bus Stop #N` and `Bicycle Corridor #N`. They are consistent across map tooltips, ranking, and inspector. The separate **Rank** shows priority order, which may differ from the candidate number. Full IDs are available in expandable details with a copy button and manual-copy fallback.
- Priority is described as modeled intervention need, not certainty, safety, or approval. Bus `population_affected` is labeled newly covered population, following its existing methodology. It is not substituted for simulation `population_improved`; benefits are never summed across proposals.
- Previously 7–11 px panel text is now 12–14 px, with improved wrapping and spacing. Desktop panels have bounded independent scrolling; expanding priorities or layers leaves space for the other panel on that side. At widths up to 1,100 px the map and panels form a scrollable column. This trades simultaneous map/panel visibility for readable, reachable content on small screens.
- Static data is labeled “Static data,” rather than “Prototype data.”

## Measurements

Observed in isolated headless Chrome, 1,440 × 1,000 CSS pixels, device scale 1, using the local Vite development server and the actual complete datasets. OSM tile requests were blocked in both measurements to isolate vector rendering. No CPU/network throttling was applied. These are individual observations, not production benchmarks or statistical guarantees.

| Characteristic | Original implementation | Final implementation |
| --- | ---: | ---: |
| SVG paths across the document | 36,810 | 1,781 |
| Grid SVG paths | 35,029 | 0 (one Canvas) |
| Document elements | 37,037 | 2,012 |
| Observed initial ready time | 4.09 s | 1.91 s |
| Observed Overall → Bus switch settling time | 3.47 s | 0.39 s |
| HTML elements created during that switch | 140,116 | 0 |
| Observed initial native `keydown` registrations | 36,820 | 1,791 |

Initial readiness was polled after navigation until datasets had loaded and rendered, followed by two animation frames; the measurement has polling/scheduling overhead. Switch timing includes browser-protocol input delivery and two animation frames after the click. Other updated runs observed switch times of 0.21–0.24 s. Counters used `document.createElement` and native event-listener instrumentation; they are not counts of all Leaflet internal listeners. The original grid pane's shared SVG container remained in place even while its individual features were recreated, so container identity alone was not used as evidence of reuse.

The regression test separately observes Leaflet calls and confirms **all 35,029 feature objects retain identity**, the metric causes **zero GeoJSON `addData` calls**, colors match the selected property, and no cell has an individually bound tooltip.

Remaining limits: the grid file is still 27,128,108 bytes before HTTP compression. Fetching/parsing/validation and initial creation remain substantial. Canvas still draws many paths and Leaflet performs linear hit testing over its paths; this is not a tiled or spatially indexed renderer. Metric switches still restyle all grid cells. Initial development loading also retains the existing React StrictMode behavior. Production hosting compression/caching and viewport-based data delivery could reduce further costs, but were not changed here. Tile loading and real-device touch performance were not benchmarked. The existing frontend does not yet load `intervention_scenarios.json`; that file and its semantics remain unchanged.

## Verification

Run from the repository root:

```bash
cd ~/projects/transporttech-integrated
npm run lint
npm run build
node tests/presentation.test.mjs
```

The four pure presentation tests cover rounding, metre/kilometre display, null/zero handling, reason mapping, complete IDs, stable labels and non-mutation.

For the dependency-free browser regression test, use an isolated Chrome profile (Node 22+ with built-in WebSocket):

```bash
# Terminal 1
npm run dev -- --host 127.0.0.1 --port 5173

# Terminal 2: temporary profile, not your normal browser profile
google-chrome --headless --remote-debugging-port=9222 \
  --user-data-dir="$(mktemp -d /tmp/transporttech-browser.XXXXXX)" about:blank

# Terminal 3
node tests/map-browser-check.mjs
```

The browser test uses the development-only QA fixtures and Vite's loaded Leaflet module to observe identity without changing datasets. It blocks OSM tiles, checks metric switching, tooltip content, mouse/keyboard selection, selection halos, blank-map clearing, Escape, pan/zoom, grid visibility, IDs/copy, readable reasons, 320/390/768/1,024 px layouts, null/empty states, and runtime exceptions. Browser testing here used a headless process launched with `--no-sandbox` inside the isolated execution environment; normal local Chrome should use its default sandbox.

All requested lint/build checks, four presentation tests, and browser regression checks passed. SHA-256 checks of the 78 protected backend/public-data files found no changes. No dependency was installed, and no commit or push was made.

## Changed files

- Map lifecycle/integration: `src/App.jsx`, `src/components/MapLayers.jsx`, new `GridLayer.jsx`, `MapSelectionController.jsx`, `MapFocusController.jsx`.
- Display/interaction: new `src/utils/presentation.js`, new `GridBrowser.jsx`, new `FeatureIdentifier.jsx`, `AnalysisPanel.jsx`, `DetailsPanel.jsx`, `PriorityRanking.jsx`, `SummaryPanel.jsx`, `AppHeader.jsx`.
- Styles: `src/App.css`, component CSS for `AnalysisPanel`, `DetailsPanel`, `PriorityRanking`, `SummaryPanel`, `LayerPanel`, and `DataStatus`.
- Verification/report: `tests/presentation.test.mjs`, `tests/map-browser-check.mjs`, this file.

`src/data/validateData.js`, `SelectedFeatureLayer.jsx`, package manifests, and input datasets were inspected and left unchanged. Existing modifications under `public/data/` were already present when work started.
