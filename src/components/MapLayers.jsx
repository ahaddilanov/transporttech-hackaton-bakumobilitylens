import L from 'leaflet'
import { GeoJSON } from 'react-leaflet'

const METRIC_LABELS = {
  mobility_gap: 'Mobility gap',
  bus_priority: 'Bus priority',
  bike_priority: 'Bike priority',
}

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

function showValue(value, suffix = '') {
  if (value === null || value === undefined) {
    return 'Unavailable'
  }

  if (typeof value === 'number') {
    return `${value.toLocaleString()}${suffix}`
  }

  return `${value}${suffix}`
}

function createTooltipContent(title, rows = []) {
  const container = document.createElement('div')
  container.className = 'transport-tooltip-content'

  const titleElement = document.createElement('strong')
  titleElement.textContent = title

  container.appendChild(titleElement)

  rows.forEach((row) => {
    if (!row) {
      return
    }

    const rowElement = document.createElement('span')
    rowElement.textContent = row

    container.appendChild(rowElement)
  })

  return container
}

function bindTooltip(layer, title, rows = []) {
  layer.bindTooltip(
    createTooltipContent(title, rows),
    {
      className: 'transport-tooltip',
      direction: 'top',
      sticky: true,
      opacity: 0.96,
      offset: [0, -6],
    }
  )
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
            const properties = feature.properties

            bindTooltip(
              layer,
              'Analysis cell',
              [
                `ID: ${properties.id}`,
                `${
                  METRIC_LABELS[selectedMetric]
                }: ${showValue(
                  properties[selectedMetric]
                )}/100`,
              ]
            )

            layer.on('click', () => {
              selectFeature(
                'Grid cell',
                feature
              )
            })
          }}
        />
      )}

      {visibility.busRoutes &&
        busRoutes && (
          <GeoJSON
            data={busRoutes}
            style={{
              color: '#2563eb',
              weight: 4,
              opacity: 0.8,
            }}
            onEachFeature={(
              feature,
              layer
            ) => {
              const properties =
                feature.properties

              bindTooltip(
                layer,
                properties.name ??
                  'Bus route',
                [
                  `Route: ${showValue(
                    properties.route_ref
                  )}`,
                  `Daily validations: ${showValue(
                    properties.avg_daily_validations
                  )}`,
                ]
              )

              layer.on('click', () => {
                selectFeature(
                  'Bus route',
                  feature
                )
              })
            }}
          />
        )}

      {visibility.cycleways &&
        cycleways && (
          <GeoJSON
            data={cycleways}
            style={{
              color: '#16a34a',
              weight: 4,
              opacity: 0.8,
            }}
            onEachFeature={(
              feature,
              layer
            ) => {
              const properties =
                feature.properties

              bindTooltip(
                layer,
                properties.name ??
                  'Cycleway',
                [
                  `Length: ${showValue(
                    properties.length_m,
                    ' m'
                  )}`,
                ]
              )

              layer.on('click', () => {
                selectFeature(
                  'Cycleway',
                  feature
                )
              })
            }}
          />
        )}

      {visibility.busStops &&
        busStops && (
          <GeoJSON
            data={busStops}
            pointToLayer={(
              feature,
              latlng
            ) =>
              L.circleMarker(latlng, {
                radius: 7,
                weight: 2,
                fillOpacity: 0.8,
              })
            }
            onEachFeature={(
              feature,
              layer
            ) => {
              const properties =
                feature.properties

              bindTooltip(
                layer,
                properties.name ??
                  'Bus stop',
                [
                  `ID: ${properties.id}`,
                ]
              )

              layer.on('click', () => {
                selectFeature(
                  'Bus stop',
                  feature
                )
              })
            }}
          />
        )}

      {visibility.metroStations &&
        metroStations && (
          <GeoJSON
            data={metroStations}
            pointToLayer={(
              feature,
              latlng
            ) =>
              L.circleMarker(latlng, {
                radius: 9,
                weight: 3,
                fillOpacity: 0.9,
              })
            }
            onEachFeature={(
              feature,
              layer
            ) => {
              const properties =
                feature.properties

              bindTooltip(
                layer,
                properties.name ??
                  'Metro station',
                [
                  `Daily entries: ${showValue(
                    properties.avg_daily_entries
                  )}`,
                ]
              )

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
            pointToLayer={(
              feature,
              latlng
            ) =>
              L.circleMarker(latlng, {
                radius: 10,
                color: '#7c3aed',
                weight: 3,
                fillColor: '#a78bfa',
                fillOpacity: 0.9,
              })
            }
            onEachFeature={(
              feature,
              layer
            ) => {
              const properties =
                feature.properties

              bindTooltip(
                layer,
                'Candidate Bus Improvement',
                [
                  `Priority: ${showValue(
                    properties.priority
                  )}/100`,
                  `Population affected: ${showValue(
                    properties.population_affected
                  )}`,
                ]
              )

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
            onEachFeature={(
              feature,
              layer
            ) => {
              const properties =
                feature.properties

              bindTooltip(
                layer,
                'Candidate Bicycle Corridor',
                [
                  `Priority: ${showValue(
                    properties.priority
                  )}/100`,
                  `Length: ${showValue(
                    properties.length_m,
                    ' m'
                  )}`,
                  'Further engineering assessment',
                ]
              )

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