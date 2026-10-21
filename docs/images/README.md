# Application screenshots

## Real application outputs

The project owner supplied the following screenshots of the real Baku application.
The filenames are retained exactly as received, including the shortened
`recommendatio` name and doubled `.png.png` extension. Dimensions below were read
from the PNG headers. Capture dates, browser settings and the exact source-data
revision were not supplied and are not inferred from filesystem timestamps.

| File | Visible state | Dimensions |
| --- | --- | --- |
| `baku-real-overview.png` | Overall accessibility priority grid and transport layer controls | 1920 × 942 |
| `baku-real-recommendatio.png` | Selected bus candidate inspector alongside the rankings | 1920 × 944 |
| `baku-real-before-after.png.png` | Candidate inspector with Before / After accessibility collapsed | 1920 × 945 |

These are real project outputs, but their candidate infrastructure and estimated
accessibility improvements are hypothetical. The before/after file does not
show the expanded scenario metrics; an additional capture with that section
expanded would be needed to illustrate those real values. The synthetic gallery
separately shows the expanded interface with illustrative numbers.

All three supplied images retain visible OpenStreetMap attribution at the lower
right. They were not cropped, resized or otherwise edited in this update.
Screenshots do not grant permission to redistribute underlying datasets.
Third-party data and basemap terms remain separate from the MIT source-code
license; see the [source audit](../../backend/DATA_SOURCES.md).

## Synthetic demo screenshots

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

### Reproduce the synthetic views

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
