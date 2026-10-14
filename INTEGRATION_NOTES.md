# TransportTech baseline integration notes

Integrated the first real backend baseline package into the existing React/Vite/React-Leaflet frontend without redesigning the UI.

## Real baseline datasets

Loaded from `public/data` through the existing `/data/<filename>` static URLs:

- `grid.geojson` — 35,029 analysis cells
- `bus_stops.geojson` — 1,414 mapped bus stops
- `bus_routes.geojson` — 243 AYNA route features
- `metro_stations.geojson` — 27 metro stations
- `cycleways.geojson` — 60 bicycle-lane features
- `summary.json` — baseline statistics

Bus and bicycle recommendation files are intentionally absent from this baseline package.

## Frontend changes

- Replaced all mock baseline GeoJSON/JSON files with the real backend files.
- Removed the mock recommendation GeoJSON files from `public/data`.
- Stopped loading and rendering recommendation datasets for this baseline phase.
- Hid the intervention ranking and proposed-improvement layer controls until real recommendation datasets exist.
- Changed the header badge from `Prototype data` to `Baseline data` for static baseline mode.
- Preserved the exact backend contract property names.
- Added grid data-quality context for `scoring_quality`, `coverage_status`, `valid_pixel_fraction`, and optional `scoring_model_version`.
- Clarified route validations as route-level context.
- Kept `null` distinct from numeric zero throughout score colors and Inspector values.
- Added compact baseline source attribution/limitations text to the layer panel.

## Performance change for the full grid

The 35,029-cell analysis grid now uses a dedicated Leaflet Canvas renderer instead of creating tens of thousands of SVG DOM paths. Grid tooltips are also created lazily on hover instead of eagerly for every cell. Existing bus/metro/cycleway vector layers remain SVG so their prior keyboard behavior is preserved.

## Verified in this integration workspace

- Backend feature counts and unique IDs.
- Geometry-type compatibility with Contract V1.
- Plausible EPSG:4326 `[longitude, latitude]` coordinate order.
- All non-null priority scores are numeric and within 0–100.
- `null` priority scores remain null and are not converted to zero.
- Summary high-priority counts reproduce the backend reporting rule using its supplied threshold.
- Population estimate matches the sum of available modeled grid populations.
- Route-level validation averages remain only on route features; no stop-to-route or stop-ridership relationship was invented.
- Existing frontend validators accept all six baseline datasets.
- JS/JSX syntax parsing passes for the complete `src` tree.

## Local verification commands

From the frontend root:

```powershell
npm install
npm run lint
npm run build
npm run dev
```

Then open the exact Vite `Local:` URL and verify the real layers, score switching, Inspector, layer toggles, light/dark mode, and map responsiveness.

Note: browser rendering could not be executed in the integration sandbox because npm registry access is unavailable there, so the final interactive performance check must be run on the normal development machine where project dependencies are installed.
