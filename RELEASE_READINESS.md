# Baku Mobility Lens — release readiness

Updated **2026-10-21**, branch `integration/backend-and-scenarios`, inspected
HEAD `6d4e934` (`Remove tracked Visual Studio workspace artifacts`). Release
preparation (`34b326f`) and frontend regression tests (`92a9674`) are already
committed. The owner reports those changes were pushed; no fetch or remote
visibility change was performed in this task.

**Original-code MIT approval is resolved. Data redistribution and historical
real-data exposure remain separate release blockers.** This task adds license
and documentation assets only. Nothing was staged, committed, pushed or merged;
PR #1 was not merged. No history, calculations or dataset bytes were changed.

## Completed work and exact changed files

| File | Change |
| --- | --- |
| `LICENSE` | Added complete standard MIT text, approved by both original code contributors |
| `README.md` | Reorganized overview, three actual synthetic-demo screenshots, two native Mermaid diagrams, approved license and explicit data boundaries |
| `CONTRIBUTORS.md` | Replaced pending-license text with both contributors' approval |
| `backend/DATA_SOURCES.md` | Updated original-code license row; retained third-party rights blockers |
| `demo/README.md` | Updated original synthetic-fixture license reference |
| `docs/DEVELOPMENT.md` | Preserved detailed backend setup, acquisition/export workflow, folder structure and unchanged Contract V1 reference from the README |
| `docs/images/README.md` | Capture provenance, reproduction steps, sizes and basemap attribution |
| `docs/images/synthetic-overview.jpg` | Actual demo map, scoring and layers screenshot |
| `docs/images/synthetic-inspector.jpg` | Actual selected synthetic candidate screenshot |
| `docs/images/synthetic-before-after.jpg` | Actual expanded synthetic comparison screenshot |
| `RELEASE_READINESS.md` | Current verification, approval status and publication boundaries |

No frontend source, package manifest/lockfile, backend calculation, methodology,
contract or fixture was edited. The eight pre-existing modified real files in
`public/data/` remain untouched and unstaged. They are not changes from this task.

## Screenshots and diagrams

Three full-viewport 1600 × 1100 JPEG screenshots, total **1,485,246 bytes**, show
the working synthetic demo with online OSM tiles. The synthetic header and OSM
attribution are visible in each image. No real transport overlays, fabricated
dashboards, personal information or cropped attribution are included. No further
manual screenshots are required. Historical external screenshot links were
replaced, without deleting or modifying remote attachments.

Both README Mermaid blocks parsed and rendered to SVG in an isolated browser
using Mermaid 11.12.0 through its documented CDN loading method: architecture
6 nodes / 5 edges; workflow 5 nodes / 4 edges. No dependency was installed or
added to the project. This checks actual Mermaid rendering; a final GitHub
preview is still useful because GitHub controls its renderer version.

## Actual verification results

| Check | Result |
| --- | --- |
| `npm run lint` | Passed |
| `npm test` | Passed all 4 test files; no failures or skips |
| `npm run build:demo` | Passed; 91 modules, synthetic output in `dist-demo/` |
| `npm run build` | Passed; 91 modules, local real-data output in `dist/` |
| `npm run test:real-data` | Passed the real-snapshot scenario consistency test file |
| `APP_URL=http://127.0.0.1:5174/ node tests/demo-browser-check.mjs` | Passed synthetic counts/labels, keyboard and ranking selection, bus/bike comparisons, no hover tooltips, mobile layout; no unhandled runtime exceptions |
| Backend `python -m unittest discover -s tests -v` | 84 tests passed using the existing Python 3.14.7 environment; no dependencies installed |
| Protected-file SHA-256 comparison | All 118 checked files unchanged: frontend source, real and demo data, backend scripts/config/tests/data |
| MIT text | Full permission, condition and disclaimer match standard MIT text after whitespace normalization; checked against an existing MIT package license and the OSI reference |
| Documentation links | Local Markdown file/image targets resolve |
| Git index | Empty; no real/generated data staged |

Browser smoke checks deliberately block tile requests for repeatability;
screenshots were separately captured with actual tiles loaded. No new zoom
performance claim is made. Frontend source is unchanged, and existing browser
regressions passed. Ordinary build output includes local real data and must
remain local; a successful build is not permission to publish it.

Current real-data counts were read directly from the local JSON/GeoJSON:
35,029 grid cells; 1,414 stops; 243 routes; 27 metro stations; 60 cycleway
features; 20 bus candidates; 14 bicycle candidates; 34 scenarios (20 bus,
14 bicycle). These are not synthetic-demo counts. The demo contains four cells,
one candidate of each type and two illustrative saved comparisons.

## Reproducibility

A clone of the integration branch can install dependencies with `npm ci`, run
`npm run dev:demo`, `npm test` and `npm run build:demo` without private source
inputs. Online OSM background tiles need internet access. Demo mode isolates
`demo/public/` from the local real `public/` overrides. The normal tracked
fixtures lack scenarios; the frontend reports them unavailable gracefully.

Full Baku processing is **not** reproducible from a clone alone. Authorized raw
inputs, provenance/version evidence and a compatible geospatial Python/native
environment are required. Direct Python dependencies are pinned, but the full
transitive/native environment is not locked. See [development instructions](docs/DEVELOPMENT.md)
and the [data inventory](backend/DATA_INVENTORY.md). No protected analysis was
regenerated during this documentation task.

## Licensing and remaining publication blockers

Both @osmanveyisli and @ahaddilanov explicitly approved MIT for their original
source code. The [LICENSE](LICENSE) copyright line is:

> Copyright (c) 2026 osmanveyisli and ahaddilanov

The complete standard text follows the [OSI MIT reference](https://opensource.org/license/mit).
This approval does not relicense dependencies, OSM, WorldPop, geoBoundaries,
OpenData.az or AYNA-attributed data. Attribution alone is not redistribution
permission. See the [precise data-rights audit](backend/DATA_SOURCES.md#public-release-data-rights-audit--2026-10-21).

Remaining gates for **real-data publication**:

1. Verify AYNA geometry provenance and redistribution/public-display rights,
   including derived recommendations, study areas, grids, scenarios and exports.
2. Establish resource-specific OpenData.az terms and exact-source provenance for
   validations, metro records and POIs.
3. Resolve the geoBoundaries pinned-release license discrepancy against the exact
   source metadata; do not infer historical terms from the current website.
4. Prepare artifact-specific OSM/ODbL and WorldPop notices and assess obligations
   for mixed-source derivatives. These datasets are not MIT-licensed.
5. Review historical branches, attachments, releases and copies. The previous
   audit found real baseline data in `9a8358d`, locally referenced by
   `origin/real-baseline-integration`, outside this integration branch's ancestry.
   Current server-side state was not checked. Do not merge PR #1 or publish those
   assets as a consequence of this documentation update.

The current index no longer tracks `.vs/` artifacts following `6d4e934`. That
resolves the current-tree IDE cleanup; it does not erase historical artifacts.
Historical privacy/rights review remains an owner decision. No history rewrite
or remote cleanup was attempted.

## Safe review scope and files that remain local

The eleven files listed above are the intended license/documentation review
scope. The three screenshot basemaps retain their third-party attribution and
terms. Review them as attributed screenshots, not as wholly MIT-owned imagery.

Keep all eight real `public/data/` overrides and the local scenario JSON out of
this commit. Keep backend raw/processed data, GraphML networks, complete exports,
ZIPs, ordinary `dist/`, local environments, caches and secrets local. Existing
ignore rules do not prevent staging modifications to already tracked data.
Do not use `git add .`, `git add -A`, or `git commit -a` for this change.

## Suggested next Git commands

Review and stage only the intended files after the owners inspect the results:

```bash
git status --short
git diff --check
git diff -- README.md CONTRIBUTORS.md RELEASE_READINESS.md backend/DATA_SOURCES.md demo/README.md
git add -- LICENSE README.md CONTRIBUTORS.md RELEASE_READINESS.md \
  backend/DATA_SOURCES.md demo/README.md docs/DEVELOPMENT.md \
  docs/images/README.md docs/images/synthetic-overview.jpg \
  docs/images/synthetic-inspector.jpg docs/images/synthetic-before-after.jpg
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
# Only after confirming the staged list contains exactly these eleven files:
git commit -m "Add approved MIT license and synthetic application visuals"
```

These are suggestions, not executed commands. No push or merge is included.
The eight real-data overrides should still appear as unstaged modifications.
