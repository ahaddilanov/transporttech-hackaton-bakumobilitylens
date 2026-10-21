# Baku Mobility Lens — release readiness

Audit date: **2026-10-21**. Branch: `integration/backend-and-scenarios`.
Inspected HEAD: `92a9674` (`Add frontend interaction and simulation regression tests`).
Recorded origin: `https://github.com/baku-mobilitylens-team/baku-mobility-lens.git`.

**Status: release preparation implemented and locally verified; public release
remains blocked by code-licensing, data-rights and historical-artifact review.**
No commit, staging, push, merge, remote change, visibility change, history rewrite,
reset, clean, stash or repository transfer was performed. Existing useful local
work and real datasets were preserved. These proposed changes are not yet
available from a remote clone until the developers review and commit them.

## 1. Completed changes

- Replaced the outdated README with the actual implemented scope, verified
  snapshot counts, architecture, setup/testing instructions, data prerequisites,
  processing/export order, V1 field reference, limitations and future work.
- Added contributor roles and GitHub links without changing commit authorship.
  Updated the page/header identity to **Baku Mobility Lens**.
- Linked the existing visible OSM map credit to the provider's copyright/license
  page. This does not clear the other provider-data publication gates.
- Added a small original synthetic UI demo, visibly labeled, with made-up geometry
  and numerical examples. Its generator reads no real data and writes only its
  dedicated demo directory. It includes two illustrative saved comparisons.
- Isolated demo development/build assets using Vite's existing mode mechanism;
  `build:demo` cannot copy local `public/data/` into its output. Normal static/API
  behavior and the real-data build remain available.
- Added clone-safe npm test/setup scripts. Moved real-snapshot assertions into an
  explicit real-data suite; preserved their full-ID and five-policy-difference
  checks. Added synthetic-data, build-isolation and browser smoke checks.
- Expanded ignore rules for local environments, IDE files, Python caches and the
  local real scenario JSON. No tracked file was automatically removed.
- Excluded the generated demo build from ESLint alongside the existing normal
  build exclusion, so lint remains repeatable after either build.
- Audited data attribution separately from redistribution rights; dated the early
  inventory as historical and recorded current processed availability. Replaced
  two obsolete personal absolute command paths with the integrated backend path.
- Retained existing screenshot references with historical/publication caveats.

## 2. Exact task-changed files

Existing tracked files edited by this task:

```text
.env.example
.gitignore
FRONTEND_SIMULATIONS.md
README.md
backend/BIKE_RECOMMENDATIONS_METHODOLOGY.md
backend/DATA_INVENTORY.md
backend/DATA_SOURCES.md
backend/SIMULATION_METHODOLOGY.md
eslint.config.js
index.html
package.json
src/App.jsx
src/components/AppHeader.jsx
src/data/dataSources.js
tests/scenarios.test.mjs
vite.config.js
```

New files:

```text
CONTRIBUTORS.md
RELEASE_READINESS.md
demo/README.md
demo/public/favicon.svg
demo/public/data/grid.geojson
demo/public/data/bus_stops.geojson
demo/public/data/bus_routes.geojson
demo/public/data/metro_stations.geojson
demo/public/data/cycleways.geojson
demo/public/data/bus_recommendations.geojson
demo/public/data/bike_recommendations.geojson
demo/public/data/summary.json
demo/public/data/intervention_scenarios.json
scripts/create_demo_data.mjs
tests/demo-browser-check.mjs
tests/demo-data.test.mjs
tests/scenarios-real-data.test.mjs
```

`package-lock.json` was inspected and left unchanged: scripts/identity setup adds
no dependency or lockfile version changes. Protected backend calculations,
configuration, source/processed data, recommendations, scenarios, export scripts,
backend tests and Shared Contract V1 were not modified.

Pre-existing local changes, **not authored by this task and not safe to stage**:
all eight tracked files under `public/data/` contain real replacements of mock
fixtures. The pre-existing `public/data/intervention_scenarios.json` remains
intact; it is now ignored rather than shown as untracked. No file was discarded.

## 3. Actual checks and results

Environment: Node **22.23.1**, npm **10.9.8**, Python **3.14.7**. Existing installed
packages were used; no dependency was installed. Locked runtime packages inspected:
React 19.3.0, React-Leaflet 5.0.0, Leaflet 1.9.4, Vite 8.3.3, ESLint 10.12.0.
Python direct pins match the existing environment: OSMnx 2.1.1, GeoPandas 1.2.0,
Pyogrio 0.13.0 and Rasterio 1.5.2.

| Check | Actual result |
| --- | --- |
| `npm run lint` | Passed |
| `npm test` | Passed, 4 files; 15 individual test cases also confirmed by direct file runs |
| `npm run test:real-data` | Passed; 2 full-snapshot tests, all 34 exact-ID links and five bicycle differences retained |
| `npm run build` | Passed; local `dist/` includes real files and is **not cleared for publication** |
| `npm run build:demo` | Passed; `dist-demo/data/` has exactly 9 synthetic files, byte-identical to fixtures |
| `npm ls --depth=0` | Passed, installed direct dependencies present |
| `node tests/map-browser-check.mjs` | Passed on real data: clicks, drag/release, wheel zoom, stable grid/color thresholds, keyboard/ranking/browser selection, clearing, themes, responsive sizes, null/empty states |
| `node tests/simulation-browser-check.mjs` | Passed: loading, six metrics, exact IDs, bicycle status/limitations, keyboard, null/zero/empty/404/duplicate cases and unchanged grid lifecycle |
| `APP_URL=http://127.0.0.1:5174/ node tests/demo-browser-check.mjs` | Passed against clone-equivalent demo: synthetic labels/counts, bus/bicycle comparisons, keyboard/ranking, mobile, no hover labels |
| Clone-equivalent default-mode browser check, scenario file absent | Passed: 4-cell mock map and inspector remain usable; handled load error and unavailable comparison; zero unhandled runtime exceptions |
| `python -m unittest discover -s backend/tests -v` with existing geospatial environment | **84 passed**, no skips; repeated in the data-free clone-equivalent tree: **84 passed** |
| `python backend/scripts/17_simulate_accessibility.py --verify-only` | Passed; **34** independent scalar recalculations; no writes |
| `python backend/scripts/18_export_frontend_complete.py --verify-only` | Passed; exact links, geometry/fields/nulls, source identity, ZIP contents, summary and 34 independent scenario calculations |
| `git diff --check` and local Markdown target checks | Passed |
| SHA-256 preservation manifest | All **68** protected pre-existing data/script/config/backend-test files unchanged |
| Git index | Unchanged; no staged files |

Backend export tests deliberately construct a duplicate ZIP member; Python emits
an expected duplicate-name warning for that negative test. Error fixtures in
browser tests intentionally exercise data-load errors. Browser suites completed
without unhandled runtime exceptions. OSM tile requests were blocked to isolate
local application behavior; live tile service, physical touch devices and other
operating systems were not tested. Existing measured zoom comparisons remain in
FRONTEND_PERFORMANCE.md; this release task did not produce a new zoom benchmark.

A repeat lint run initially exposed generated `dist-demo/` bundles being scanned.
The generated-output ignore was added alongside the existing `dist/` exclusion;
lint then passed both before and after both builds, including in the clone tree.
No source lint rule or test assertion was disabled.

The temporary clone-equivalent tree was assembled from tracked files, using HEAD
mock data rather than working real overrides, plus the proposed release files.
It had no real scenario file, processed datasets or raw inputs. Lint, both builds,
unit tests and demo/default-mode browser checks passed there. Installed
`node_modules` and the existing Python environment were reused. **Clean `npm ci`
and `pip install` were documented, not executed**, so a cold installation on a
new platform has not been verified. No dependencies were added.

### Counts and output checks

| Local real dataset | Count |
| --- | ---: |
| Grid / mapped stops / supplied routes | 35,029 / 1,414 / 243 |
| Metro stations / supplied cycleways | 27 / 60 |
| Bus / bicycle recommendations | 20 / 14 |
| Scenarios | 34: 20 bus; 14 bicycle |
| Reconciliation | 29 `match`; 5 `consistent_with_osm_exclusion` |

The full export ZIP is **4,337,802 bytes**. Display-route maximum deviation is
**4.999870307 m**, independently checked against the existing 5 m simplification
limit. The real grid alone is **27,128,108 bytes**. All nine synthetic data files
together are **11,349 bytes**. The synthetic counts are 4 cells, 2 stops, 1 route,
1 metro station, 1 existing cycleway, 1 bus candidate, 1 bicycle candidate and
2 fabricated saved comparisons. These are UI examples, not modeled findings.

No individual intervention population benefits were added into a portfolio total.

## 4. Fresh-clone and full-analysis reproducibility

**Frontend demo:** prepared for a fresh clone after these files are committed.
Use the README's Node requirement, `npm ci` and `npm run dev:demo`. Demo mode
loads all nine synthetic files and ignores API configuration. A demo build uses
only `demo/public/`; ordinary `public/data/` is preserved. Background tiles need
internet access and provider attribution/policy compliance.

**Current tracked default fixtures:** usable but incomplete as a scenario demo:
4 grid cells, 3 stops, 2 routes, 2 metro stations, 2 cycleways, 2 bus candidates,
2 bicycle candidates and no scenario file. The absent scenario path is caught
rather than crashing the app. On Vite a missing JSON path may return the HTML
fallback and cause a handled JSON parse error rather than an HTTP 404; available
layers still render. Synthetic demo mode avoids that incomplete default state.

**Full Baku analysis:** not reproducible from a clone alone. The integrated
`backend/data/raw/` has only `.gitkeep`. Authorized AYNA originals, OpenData CSVs,
POI source, population raster, boundary and original OSM snapshots/cache must be
obtained or restored at the paths documented in README/DATA_SOURCES.md. Historical
OSM stop retrieval time is unknown; live retrievals can change results. Direct
Python requirements are pinned but transitive/native dependencies and platforms
are not completely locked. Exact historical reproduction needs matching source
bytes, hashes, configuration, versions and environment.

All synthetic backend unit tests run without these inputs. Real raw-dependent
processing/verification stages (including infrastructure normalization from KMZ/
CSVs, raster/grid regeneration and POI selection) were not run because raw inputs
are missing here and rebuilding data is outside this task. Acquisition scripts
were not run; no graph was downloaded. Saved simulation/export verification works
locally because the processed prerequisites are present. It will fail clearly in
a clone without those prerequisites, as intended.

## 5. Licensing and attribution blockers

1. **Original code:** no LICENSE exists. Recommend the
   [MIT license](https://opensource.org/license/mit) for original code, subject to
   **both contributors' approval** and ownership review. No license was added.
2. **AYNA-attributed geometry:** redistribution rights are unverified for all four
   supplied resources. Hold route/lane originals and derivatives, recommendations,
   study geometry, mixed-source grids/scenarios/exports and public displays pending
   scope review. Attribution alone is not permission.
3. **OpenData.az:** establish resource-specific terms and provenance for exact
   route/day, station/day, metro-coordinate and POI source files and derivatives.
4. **geoBoundaries:** current website says CC BY 4.0; earlier project notes say
   CC BY-SA 3.0. Resolve against the pinned AZE ADM2 release and upstream metadata.
   Pinned metadata retrieval did not succeed during this audit.
5. **OSM/WorldPop:** prepare artifact-specific data notices and license evidence,
   including ODbL obligations and recorded WorldPop CC BY 4.0 product attribution.
   Existing embedded evidence does not give mixed-source packages one license.
6. **Screenshots:** two earlier GitHub attachment references remain in README.
   Their content/permission/visible attribution needs review. Retrieval through
   the browsing tool failed; continued availability was not confirmed. Do not
   infer that historical publication clears current rights.

Evidence links, per-source distinctions and precise affected data paths are in
[DATA_SOURCES.md](backend/DATA_SOURCES.md#public-release-data-rights-audit--2026-10-21).
These are unresolved publication gates, not legal clearance conclusions.

## 6. GitHub and repository hygiene blockers

A scan of **228 reachable historical blobs** and current tracked files found no
matches for the selected private-key, GitHub-token, AWS-key and assigned-secret
patterns. Only `.env.example` is tracked; no local `.env` was found. This is a
limited pattern scan, **not a comprehensive secret/security certification**.

No node_modules, dist, Python virtual environment/cache or generated backend
network/export file is tracked in the current tree. Six Visual Studio artifacts
are already tracked and remain untouched:

```text
.vs/VSWorkspaceState.json
.vs/slnx.sqlite
.vs/transporttech-frontend.slnx/FileContentIndex/ae505e62-31ee-4303-b6f7-de5aa3b8eadd.vsidx
.vs/transporttech-frontend.slnx/v18/.wsuo
.vs/transporttech-frontend.slnx/v18/DocumentLayout.backup.json
.vs/transporttech-frontend.slnx/v18/DocumentLayout.json
```

They include workspace/index metadata and a personal filesystem-path finding.
New ignore rules prevent new artifacts, but **do not untrack existing files**.
Owner-reviewed index removal is suggested below; local copies can be kept. IDE
history/privacy review is separate from source-code attribution; no history was
rewritten. The two personal absolute backend command paths were corrected in
documentation; historical generic Downloads references remain provenance notes.

### Real data on a separate recorded branch

Commit **`9a8358d`**, `Integrate real baseline mobility datasets`, is recorded at
**`origin/real-baseline-integration`**. It contains:

```text
public/data/grid.geojson             35,029 cells
public/data/bus_stops.geojson         1,414 stops
public/data/bus_routes.geojson        243 routes
public/data/metro_stations.geojson    27 stations
public/data/cycleways.geojson         60 lane features
public/data/summary.json              real baseline summary
```

This commit is **not an ancestor of the current integration branch**. It is
reachable through a different local remote-tracking ref. Current server-side
refs/visibility were not fetched or authenticated during this audit. A new clean
commit on this branch does not resolve the repository-wide rights issue on that
other recorded branch. Owners must review current GitHub branches, assets,
attachments and copies before making any visibility/public-release decision.
Do not automatically delete refs, rewrite either contributor's history or assume
that an ordinary removal commit removes previously distributed data.

The existing seven frontend regression/helper files are already tracked at HEAD
(including the previously untracked tests). New release tests listed above are
intentional additions; tests are not ignored. Local documentation link targets
were checked. Legacy package naming is retained to avoid unnecessary lockfile
churn; public identity is Baku Mobility Lens.

## 7. Files safe to review/commit; files that must stay local

The **33 task-changed files listed in section 2** are the proposed source/docs/
original-synthetic-fixture staging set, subject to normal developer review.
Screenshot references remain a publication gate even within that documentation.
This list does not grant provider-data rights or adopt the proposed code license.

Keep these local until the corresponding rights review is complete:

- All current real overrides under `public/data/`, including its ignored scenario
  file. Eight paths remain tracked, so `git add .` / `git add -A` is unsafe here.
- All raw resources, `backend/data/processed/`, networks, complete exports/ZIP,
  OSM caches, and normal local `dist/` containing real data.
- `.venv/`, node_modules, `.env*` secrets/local settings, caches and IDE state.
  `.env.example` is an intentionally non-secret tracked exception.
- New screenshots or other real-data publication assets pending clearance.

`dist-demo/` is a generated synthetic build, not a source commit target. It does
not contain the real exports, but hosting still needs the code-license decision
and normal tile-provider/asset review. Existing historical real-data and IDE
objects require owner review independently of working-tree ignores.

## 8. Suggested next Git commands — review manually, do not push yet

Run from this repository, after reviewing the proposed changes. These are
**suggestions, not commands executed by this task**. Do not use broad staging.

```bash
git branch --show-current
git status --short --untracked-files=all
git diff --check
git diff -- README.md .gitignore .env.example package.json vite.config.js eslint.config.js index.html
git branch -a --contains 9a8358d
git ls-tree -r 9a8358d public/data

# Explicit source/documentation/original-synthetic staging only:
git add -- .env.example .gitignore README.md CONTRIBUTORS.md RELEASE_READINESS.md FRONTEND_SIMULATIONS.md
git add -- backend/DATA_SOURCES.md backend/DATA_INVENTORY.md backend/BIKE_RECOMMENDATIONS_METHODOLOGY.md backend/SIMULATION_METHODOLOGY.md
git add -- index.html package.json vite.config.js eslint.config.js src/App.jsx src/components/AppHeader.jsx src/data/dataSources.js
git add -- scripts/create_demo_data.mjs tests/scenarios.test.mjs tests/scenarios-real-data.test.mjs tests/demo-data.test.mjs tests/demo-browser-check.mjs
git add -- demo/README.md demo/public/favicon.svg demo/public/data/*.geojson demo/public/data/*.json

# Optional, after reviewing all six IDE paths: untrack while keeping local files.
git rm -r --cached -- .vs/

git diff --cached --name-status
git diff --cached --check
# Must have no staged changes at these real-data paths:
git diff --cached -- public/data/ backend/data/
```

Once the staged diff is approved and that last data check is empty, a possible
local commit is:

```bash
git commit -m "Prepare Baku Mobility Lens release docs and synthetic demo"
```

Do not push, merge or change visibility until both contributors approve the
code license and resolve the applicable data, screenshot and historical-artifact
blockers. No automatic LICENSE addition or destructive history command is
proposed. Repository transfers/renames are outside this task and were not touched.
