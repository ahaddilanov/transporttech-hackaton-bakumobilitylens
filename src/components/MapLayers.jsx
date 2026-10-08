import L from 'leaflet'
import { GeoJSON, LayersControl } from 'react-leaflet'

function getPriorityColor(score) {
  if (score === null || score === undefined) {
    return '#9ca3af'
  }

  if (score >= 75) {
    return '#dc2626'
  }

  if (score >= 50) {
    return '#f97316'
  }

  if (score >= 25) {
    return '#eab308'
  }

  return '#22c55e'
}

function MapLayers({
  busStops,
  busRoutes,
  metroStations,
  cycleways,
  grid,
  onSelect,
}) {
  return (
    <LayersControl position="topleft">
      {grid && (
        <LayersControl.Overlay checked name="Mobility Gap">
          <GeoJSON
            data={grid}
            style={(feature) => ({
              color: '#374151',
              weight: 1,
              fillColor: getPriorityColor(
                feature.properties.mobility_gap
              ),
              fillOpacity: 0.55,
            })}
            onEachFeature={(feature, layer) => {
              layer.on('click', () => {
                onSelect({
                  type: 'Grid cell',
                  properties: feature.properties,
                })
              })
            }}
          />
        </LayersControl.Overlay>
      )}

      {busRoutes && (
        <LayersControl.Overlay checked name="Bus Routes">
          <GeoJSON
            data={busRoutes}
            style={{
              color: '#2563eb',
              weight: 4,
              opacity: 0.8,
            }}
            onEachFeature={(feature, layer) => {
              layer.on('click', () => {
                onSelect({
                  type: 'Bus route',
                  properties: feature.properties,
                })
              })
            }}
          />
        </LayersControl.Overlay>
      )}

      {cycleways && (
        <LayersControl.Overlay checked name="Cycleways">
          <GeoJSON
            data={cycleways}
            style={{
              color: '#16a34a',
              weight: 4,
              opacity: 0.8,
            }}
            onEachFeature={(feature, layer) => {
              layer.on('click', () => {
                onSelect({
                  type: 'Cycleway',
                  properties: feature.properties,
                })
              })
            }}
          />
        </LayersControl.Overlay>
      )}

      {busStops && (
        <LayersControl.Overlay checked name="Bus Stops">
          <GeoJSON
            data={busStops}
            pointToLayer={(feature, latlng) =>
              L.circleMarker(latlng, {
                radius: 7,
                weight: 2,
                fillOpacity: 0.8,
              })
            }
            onEachFeature={(feature, layer) => {
              layer.on('click', () => {
                onSelect({
                  type: 'Bus stop',
                  properties: feature.properties,
                })
              })
            }}
          />
        </LayersControl.Overlay>
      )}

      {metroStations && (
        <LayersControl.Overlay checked name="Metro Stations">
          <GeoJSON
            data={metroStations}
            pointToLayer={(feature, latlng) =>
              L.circleMarker(latlng, {
                radius: 9,
                weight: 3,
                fillOpacity: 0.9,
              })
            }
            onEachFeature={(feature, layer) => {
              layer.on('click', () => {
                onSelect({
                  type: 'Metro station',
                  properties: feature.properties,
                })
              })
            }}
          />
        </LayersControl.Overlay>
      )}
    </LayersControl>
  )
}

export default MapLayers