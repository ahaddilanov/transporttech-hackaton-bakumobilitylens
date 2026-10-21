# TransportTech Backend

Goal:
Baku mobility accessibility and infrastructure recommendation system.

Team:
Backend handles data/analysis.
Frontend consumes contract-compliant outputs.

Never violate:
- frontend GeoJSON = EPSG:4326
- coordinates = [longitude, latitude]
- exposed distances = meters
- higher priority score = greater intervention need
- null means unavailable
- never invent dataset fields
- BakuBus demand is route-level only
- metro entries are not OD trips
- do not change shared field names without approval

Primary sources:
1. Existing hackathon datasets
2. OpenData.az / Azerbaijan government data
3. Other authoritative Azerbaijan sources
4. OSM / WorldPop / external sources for gaps

Current development philosophy:
small feature → run → validate → commit
do not over-engineer
do not silently refactor unrelated code
