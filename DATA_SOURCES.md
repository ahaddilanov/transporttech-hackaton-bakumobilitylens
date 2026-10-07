# Data Sources

## Baku administrative study boundary

- Source: geoBoundaries
- URL: https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/AZE/ADM2/geoBoundaries-AZE-ADM2.geojson
- Dataset: Azerbaijan ADM2 — Baku City
- Source file: geoBoundaries-AZE-ADM2.geojson
- Retrieval date: 2026-10-07
- License: CC BY-SA 3.0
- CRS: EPSG:4326
- Selected feature: Baku City
- shapeID: 54616110B61947743987915
- Geometry: MultiPolygon
- Use: Study-area boundary for clipping and downloading TransportTech datasets.
- Limitation: geoBoundaries is a research boundary dataset and is not treated as an authoritative current legal/cadastral boundary.
## Baku driving road network

- Source: OpenStreetMap
- URL: https://www.openstreetmap.org/
- Retrieval method: OSMnx 2.1.1 via Overpass API
- Retrieval date: 2026-10-07
- Network type: drive
- CRS: EPSG:4326
- Local output: data/processed/networks/baku_drive.graphml
- Coverage: Baku administrative study boundary
- Use: Routable driving-road network for transport and accessibility analysis.
- Limitation: OpenStreetMap is community-maintained rather than an official Azerbaijani government road dataset. Road geometry, access tags and completeness depend on OSM coverage at retrieval time.