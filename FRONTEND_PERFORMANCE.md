# Frontend rendering, interactions and performance

Implemented against the local `integration/backend-and-scenarios` workspace and its complete Baku datasets. No backend, Shared Contract V1, processed/exported/public dataset, score, or simulation changes are required.

## Rendering decisions

- `GridLayer.jsx` creates Leaflet geometry once per dataset. Metric changes call `setStyle`; they do not use `key={selectedMetric}`, recreate GeoJSON, or replace the Canvas. Hiding/showing the grid reuses the same feature objects.
- Only the 35,029-cell grid uses Canvas. The smaller transport layers retain SVG, click selection, CSS styling, and keyboard interaction. A memoized transport-layer component avoids unrelated styling work when the grid metric changes.
- Inspection is click-only across all layers. There are no automatic hover tooltips or hover style handlers. The grid has one shared click handler, with no per-cell tooltip objects, keyboard handlers or SVG elements. Leaflet still maintains feature objects and internal event relationships.
- `ClickOnlyCanvas.js` disables Canvas mousemove hover scanning. Mousedown/up and double-click events reach the map without polygon hit tests; only a genuine, stationary click tests grid paths. Motion guards reject mouse inspection during dragging, inertia, zooming and map-focus movement. Ranking and keyboard actions remain explicit selection paths.
- A bounds index restricts the renderer's projection, clipping, drawing and click working set to the viewport plus a 15% geographic margin, slightly exceeding Canvas's 10% clip padding. All 35,029 original feature objects remain attached and retain full geometry. An alternative that attached/detached thousands of layers on every move was measured and discarded because layer lifecycle work made zooming slower.
- Grid projection is cached against zoom and pixel origin and performed in the target view's update pass. Queued redundant redraw frames are cancelled. The full Leaflet membership/order list stays intact; the renderer uses a separate visible draw list.
- Canvas feature clicks stop propagation; empty Canvas clicks clear selection. The separate SVG selection halo remains visible above all map layers. Point halos explicitly use the selection pane. Mouse focus no longer leaves an outline on an old feature; keyboard focus retains its own visible focus indicator.
- Canvas has no focusable element per cell. Skip links lead directly to analysis controls and recommendations. The analysis cell browser searches every cell by ID, displays ten at a time, and supports keyboard selection, pagination, map focus, and the existing inspector. Existing transport SVG features remain keyboard-accessible.

## Presentation decisions

- Population/count estimates display whole numbers. Distances below 1,000 m display rounded metres; distances at or above 1,000 m display kilometres with up to two decimals. Zero remains zero; null/undefined remain “Unavailable.” Values are formatted without changing the underlying properties.
- Known reason codes map to sentences; unknown reasons retain their original text. Raw reason arrays remain intact.
- Recommendation labels use source-dataset order: `Candidate Bus Stop #N` and `Bicycle Corridor #N`. They are consistent across map accessible labels, ranking, and inspector. The separate **Rank** shows priority order, which may differ from the candidate number. Full IDs are available in expandable details with a copy button and manual-copy fallback.
- Priority is described as modeled intervention need, not certainty, safety, or approval. Bus `population_affected` is labeled newly covered population, following its existing methodology. It is not substituted for simulation `population_improved`; benefits are never summed across proposals.
- Previously 7–11 px panel text is now 12–14 px, with improved wrapping and spacing. Desktop panels have bounded independent scrolling; expanding priorities or layers leaves space for the other panel on that side. At widths up to 1,100 px the map and panels form a scrollable column. This trades simultaneous map/panel visibility for readable, reachable content on small screens.
- Static data is labeled “Static data,” rather than “Prototype data.”

## Earlier SVG-to-Canvas measurements

These measurements document the completed rendering/readability stage, before the click-only zoom follow-up below.

Observed in isolated headless Chrome, 1,440 × 1,000 CSS pixels, device scale 1, using the local Vite development server and the actual complete datasets. OSM tile requests were blocked in both measurements to isolate vector rendering. No CPU/network throttling was applied. These are individual observations, not production benchmarks or statistical guarantees.

| Characteristic | Original SVG implementation | Earlier Canvas implementation |
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

## Click-only follow-up: recovery and root causes

The interrupted work already contained hover removal, motion guards, a Canvas renderer with a viewport bounds index, keyboard-listener cleanup and the point-selection pane correction. The recovered browser test had stopped while trying to return/serialize a Leaflet map from a test setup expression. Returning `void` fixes that test-harness failure. The full interaction suite and final measurements were then completed without discarding the implementation or pre-existing dataset changes.

The old transport layers bound tooltips plus mouseover/mouseout radius/weight changes to every feature. Geometry/pointer changes during drag and zoom could leave tooltip or highlight state behind. Canvas also performed linear hit tests on mouse movement and on non-inspection events such as mousedown and mouseup. These paths are removed rather than hidden with CSS. Keyboard handlers now detach on layer removal and configure idempotently on addition.

The zoom profile found one grid redraw per completed zoom, not repeated redraws throughout its CSS animation. The major CPU cost was projecting and updating all 35,029 registered cells at the end of each zoom. Existing bus routes contain 44,045 vertices across 243 features, but toggling routes had a much smaller effect. Route geometry and its existing display simplification are unchanged.

## Zoom comparison

Measured in isolated headless Chrome with Leaflet 1.9.4, Vite development mode, a 1,440 × 1,000 CSS-pixel viewport and device scale 1. All actual datasets and the other transport layers remained enabled. OSM tile requests were blocked in both runs to isolate vectors. Each case resets to the Baku overview at zoom 12, then sends three alternating wheel-in/wheel-out pairs (`deltaY=-80/+80`) at `(900, 550)`, moving between zoom 12 and 13.

| Grid | Bus routes | Earlier Canvas median settling | Final median settling |
| --- | --- | ---: | ---: |
| On | On | 582 ms | 497 ms |
| Off | On | 397 ms | 399 ms |
| On | Off | 569 ms | 475 ms |
| Off | Off | 375 ms | 374 ms |

With both layers enabled, average grid projection/update CPU time fell from **149 ms to 73 ms per zoom**. The final renderer retained all 35,029 layers but used **6,777–19,357 paths** in its render working set at the tested views. Both versions drew once per completed zoom (six draws for six wheel zooms). No pointer hit tests occurred during the separate drag, movement and wheel regression checks.

Settling time includes wheel debounce, Leaflet's existing zoom animation, protocol/polling overhead and two animation frames after completion; it is not pure CPU time or an FPS measurement. CPU totals use zoomend plus updatePaths; the nested draw/moveend timings must not be added again. These are small local samples, not production guarantees. Lag reproduced with tiles blocked, supporting grid processing as the main measured vector bottleneck; live tile/network performance remains unmeasured.

## Remaining limits and trade-offs

- The unchanged grid is 27,128,108 bytes before HTTP compression. Initial fetch, parsing, validation, feature construction and memory costs remain. Metric switches still restyle the cached grid cells.
- Click hit testing is linear over the viewport working set. Pointer movement, dragging and non-inspection pointer events do not run that scan. Large overview extents can still include most or all cells.
- Canvas still paints many visible polygons after movement and zoom. Existing animations remain enabled. Real-device touch performance, GPU frame rates and live tile loading were not benchmarked.
- The scoped renderer uses Leaflet 1.9.4 internal lifecycle methods. Leaflet upgrades require rerunning the real-data browser regression and zoom comparison. No global Leaflet prototype is changed by application code; temporary profiling wrappers exist only in the browser test scripts.
- No source GeoJSON, score/color threshold, calculation, Shared Contract V1 field or simulation result changes. No additional route simplification is implemented. The saved scenario comparison added later is documented in FRONTEND_SIMULATIONS.md. Existing development tabs should be reloaded after the update to replace any old Leaflet instances retained by hot reload.

## Verification

Run from the repository root:

```bash
cd ~/projects/transporttech-integrated
npm run lint
npm run build
node tests/presentation.test.mjs
node tests/bounds-index.test.mjs
```

Four presentation tests cover formatting, null/zero handling, reason mapping and stable IDs/labels. Two bounds-index tests independently compare indexed results with exhaustive viewport intersection checks, including boundary cells, large extents, duplicate avoidance, stable object identity and non-mutation.

For the dependency-free browser regression test, use an isolated Chrome profile (Node 22+ with built-in WebSocket):

```bash
# Terminal 1
npm run dev -- --host 127.0.0.1 --port 5173

# Terminal 2: temporary profile, not your normal browser profile
google-chrome --headless --remote-debugging-port=9222 \
  --user-data-dir="$(mktemp -d /tmp/transporttech-browser.XXXXXX)" about:blank

# Terminal 3
node tests/map-browser-check.mjs
node tests/map-zoom-comparison.mjs /tmp/transporttech-zoom-comparison.json
```

The browser test uses the development-only QA fixtures and Vite's loaded Leaflet module to observe identity without changing datasets. It blocks OSM tiles, checks all metric colors and feature identities; absence of tooltips, hover style changes and movement hit tests; clicks on every feature type; keyboard/ranking/grid-browser selection; selection halos and clearing; repeated drag/release and wheel zoom; complete viewport coverage; both themes; 320/390/768/1,024 px layouts; and null/empty states. Drag tests await inertia completion before checking the settled viewport. The suite passed without runtime exceptions. Browser testing here used a headless process launched with `--no-sandbox` inside the isolated execution environment; normal local Chrome should use its default sandbox.

The six pure tests and full browser regression checks passed. Lint and production build results are verified separately with the commands above. SHA-256 checks of the 78 protected backend/public-data files found no changes. No dependency was installed, and no commit or push was made.

## Files changed for this follow-up

- `src/components/MapLayers.jsx`: remove all hover tooltip/style handlers; retain guarded click and keyboard selection, with keyboard listener cleanup.
- `src/components/GridLayer.jsx`: shared click-only inspection and lifetime-stable geometry with the bounds index.
- New `src/components/ClickOnlyCanvas.js`: click-only pointer handling and viewport-limited renderer lifecycle.
- New `src/components/useMapInspection.js`: movement guards without React updates on every map event.
- New `src/utils/boundsIndex.js`: bounded geographic bucket search for the renderer working set.
- `src/components/MapSelectionController.jsx`: guard empty-map clearing during movement.
- `src/components/SelectedFeatureLayer.jsx`: put point halos in the intended selection pane.
- `src/App.css`: use keyboard-only focus styling instead of persistent mouse-focus outlines.
- `tests/map-browser-check.mjs`, new `tests/browser-client.mjs`, new `tests/map-zoom-comparison.mjs`, new `tests/bounds-index.test.mjs`, and this report. The existing `tests/presentation.test.mjs` is retained unchanged.

`src/App.jsx`, `MapFocusController.jsx`, unrelated frontend panels, package manifests and all backend/data files remain unchanged for this follow-up. Existing modifications under `public/data/` were already present before the task; SHA-256 checks cover 78 protected backend/public-data files. No dependency was installed, and no commit, stash, reset or push was made.
