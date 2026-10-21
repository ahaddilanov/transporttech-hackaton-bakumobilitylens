# Application screenshots

Captured on 2026-10-21 from this repository's `npm run dev:demo`, using an
isolated headless Chrome profile and the existing dependency-free CDP helper
in `tests/browser-client.mjs`. These are actual application screenshots, not
mockups or generated illustrations. No application code, styles, data or DOM
content was changed for the captures.

All three are full 1600 × 1100 viewport captures at device scale 1, JPEG quality
85, with no cropping or postprocessing. The visible header labels the synthetic
examples; map attribution remains visible at the lower right. There is no
personal browser profile or account information in the captures.

| File | State | Bytes |
| --- | --- | ---: |
| `synthetic-overview.jpg` | Overall priority grid, scoring legend and layer controls | 505,978 |
| `synthetic-inspector.jpg` | Ranked synthetic bus candidate selected, inspector expanded | 486,487 |
| `synthetic-before-after.jpg` | Same candidate with the saved comparison expanded | 492,781 |

Total: 1,485,246 bytes (about 1.42 MiB). GitHub scales the images to the available
README width; opening an image shows its full resolution.

## Reproduce the views

1. Run `npm run dev:demo -- --host 127.0.0.1 --port 5174 --strictPort` from the
   repository root and open the printed local URL in a fresh browser profile.
2. Set the viewport to 1600 × 1100 at normal zoom, light theme. Wait for tiles.
3. Collapse Mobility overview, open Map layers, and zoom in three levels using
   the map's `+` control. Capture the overview with the Overall metric active.
4. Collapse Map layers, open Priorities, and select Candidate Bus Stop #1.
   Wait for the map-focus animation and capture the inspector.
5. Expand Before / After accessibility and capture the comparison.
6. Capture the entire viewport, including the synthetic label and attribution.
   Do not crop away attribution or substitute real-data overlays.

The vector features, population figures and saved scenario values are
hand-authored [synthetic UI fixtures](../../demo/README.md), not measured Baku
findings. The recommendation and scenario display different improvements
because their illustrative values serve different UI fields; no numerical
geospatial consistency is claimed for this demo.

The basemap is real OpenStreetMap cartography, **© OpenStreetMap contributors**.
See [OSM copyright and licensing](https://www.openstreetmap.org/copyright) and
[the tile service policy](https://operations.osmfoundation.org/policies/tiles/).
The project's MIT code license does not relicense the basemap. Background map
labels and POI symbols belong to that basemap, not the synthetic overlay.
