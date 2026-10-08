import L from 'leaflet'
import { GeoJSON, LayersControl } from 'react-leaflet'

function MapLayers({
  busStops,
  busRoutes,
  metroStations,
  cycleways,
  onSelect,
}) {
  return (
    <LayersControl position="topleft">
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