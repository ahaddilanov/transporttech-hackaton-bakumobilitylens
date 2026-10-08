import L from 'leaflet'
import { GeoJSON } from 'react-leaflet'

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
  busRecommendations,
  bikeRecommendations,
  selectedMetric,
  visibility,
  onSelect,
}) {
  function selectFeature(type, feature) {
    onSelect({
      type,
      properties: feature.properties,
      feature,
    })
  }

  return (
    <>
      {visibility.grid && grid && (
        <GeoJSON
          key={selectedMetric}
          data={grid}
          style={(feature) => ({
            color: '#374151',
            weight: 1,
            fillColor: getPriorityColor(
              feature.properties[selectedMetric]
            ),
            fillOpacity: 0.55,
          })}
          onEachFeature={(feature, layer) => {
            layer.on('click', () => {
              selectFeature('Grid cell', feature)
            })
          }}
        />
      )}

      {visibility.busRoutes && busRoutes && (
        <GeoJSON
          data={busRoutes}
          style={{
            color: '#2563eb',
            weight: 4,
            opacity: 0.8,
          }}
          onEachFeature={(feature, layer) => {
            layer.on('click', () => {
              selectFeature('Bus route', feature)
            })
          }}
        />
      )}

      {visibility.cycleways && cycleways && (
        <GeoJSON
          data={cycleways}
          style={{
            color: '#16a34a',
            weight: 4,
            opacity: 0.8,
          }}
          onEachFeature={(feature, layer) => {
            layer.on('click', () => {
              selectFeature('Cycleway', feature)
            })
          }}
        />
      )}

      {visibility.busStops && busStops && (
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
              selectFeature('Bus stop', feature)
            })
          }}
        />
      )}

      {visibility.metroStations &&
        metroStations && (
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
                selectFeature(
                  'Metro station',
                  feature
                )
              })
            }}
          />
        )}

      {visibility.busRecommendations &&
        busRecommendations && (
          <GeoJSON
            data={busRecommendations}
            pointToLayer={(feature, latlng) =>
              L.circleMarker(latlng, {
                radius: 10,
                color: '#7c3aed',
                weight: 3,
                fillColor: '#a78bfa',
                fillOpacity: 0.9,
              })
            }
            onEachFeature={(feature, layer) => {
              layer.on('click', () => {
                selectFeature(
                  'Bus recommendation',
                  feature
                )
              })
            }}
          />
        )}

      {visibility.bikeRecommendations &&
        bikeRecommendations && (
          <GeoJSON
            data={bikeRecommendations}
            style={{
              color: '#0891b2',
              weight: 6,
              opacity: 0.9,
              dashArray: '10 6',
            }}
            onEachFeature={(feature, layer) => {
              layer.on('click', () => {
                selectFeature(
                  'Bike recommendation',
                  feature
                )
              })
            }}
          />
        )}
    </>
  )
}

export default MapLayers