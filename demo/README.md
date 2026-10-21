# Synthetic interface demonstration

All geometry, names and numbers in `public/data/` **inside this demo directory**
are original, hand-authored examples. They were not extracted, simplified or
sampled from the real processed data. Numerical coordinates place invented
rectangles and lines near the map's Baku overview; they do not represent actual
roads, infrastructure, population or proposed projects.

There are 4 cells, 2 stops, 1 route, 1 metro station, 1 existing cycleway, 1 bus
candidate, 1 bicycle candidate and 2 illustrative saved scenarios. Scenario
numbers demonstrate formatting, percentage points and the difference between
improved and newly covered population. They are **fabricated UI values**, not
geospatially computed results. Null and observed zero are both represented.
Real AYNA/OSM baseline text in the reusable inspector describes the real model;
this demo does not contain either provider's infrastructure data.

From the repository root:

```bash
npm run dev:demo
npm run build:demo
npm run preview:demo
```

Demo mode ignores `VITE_API_BASE_URL`, uses `demo/public/` as Vite's public
directory and builds to `dist-demo/`. It never copies the real `public/data/`
into that build. The map's background still uses online OpenStreetMap tiles;
the vector fixtures need no source-data download. Observe the tile provider's
[usage policy](https://operations.osmfoundation.org/policies/tiles/) for hosting.

Regenerate these exact files with `npm run demo:generate`; this only writes
`demo/public/data/`. `npm test` checks deterministic bytes, the existing V1
validators, scenario links, fixture summaries and artifact isolation.

Optional browser smoke test, using the isolated Chrome setup in
`../FRONTEND_PERFORMANCE.md`: start demo Vite on port 5174 and use a fresh
`about:blank` debugging tab, then run from the repository root:

```bash
APP_URL=http://127.0.0.1:5174/ node tests/demo-browser-check.mjs
```

The original hand-authored fixtures are covered by the project's [MIT License](../LICENSE).
This does not grant rights to real provider data or relicense OpenStreetMap
background tiles. See the root README and RELEASE_READINESS.md before publication.
