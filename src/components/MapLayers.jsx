import { memo } from 'react'
import L from 'leaflet'
import {
  GeoJSON,
  Pane,
} from 'react-leaflet'

const METRIC_LABELS = {
  mobility_gap: 'Mobility gap',
  bus_priority: 'Bus priority',
  bike_priority: 'Bike priority',
}

const ANALYSIS_PANE_STYLE = {
  zIndex: 250,
}

const EXISTING_LINES_PANE_STYLE = {
  zIndex: 300,
}

const EXISTING_POINTS_PANE_STYLE = {
  zIndex: 330,
}

const RECOMMENDATIONS_PANE_STYLE = {
  zIndex: 370,
}

/*
  The real baseline grid contains 35,029 polygons. Rendering those as
  individual SVG DOM nodes is unnecessarily expensive, so only the analysis
  grid uses Leaflet's Canvas renderer. Existing transport features remain SVG
  so their keyboard focus behavior is preserved.
*/
const GRID_RENDERER = L.canvas({
  pane: 'analysis-grid-pane',
  padding: 0.5,
  tolerance: 2,
})

function getPriorityColor(score) {
  if (
    score === null ||
    score === undefined
  ) {
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

function showValue(
  value,
  suffix = ''
) {
  if (
    value === null ||
    value === undefined
  ) {
    return 'Unavailable'
  }

  if (
    typeof value === 'number'
  ) {
    return `${value.toLocaleString()}${suffix}`
  }

  return `${value}${suffix}`
}

function showScore(value) {
  if (
    value === null ||
    value === undefined
  ) {
    return 'Unavailable'
  }

  return `${value}/100`
}

function createTooltipContent(
  title,
  rows = []
) {
  const container =
    document.createElement('div')

  container.className =
    'transport-tooltip-content'

  const titleElement =
    document.createElement('strong')

  titleElement.textContent = title

  container.appendChild(
    titleElement
  )

  rows.forEach((row) => {
    if (!row) {
      return
    }

    const rowElement =
      document.createElement('span')

    rowElement.textContent = row

    container.appendChild(
      rowElement
    )
  })

  return container
}

function bindTooltip(
  layer,
  title,
  rows = []
) {
  layer.bindTooltip(
    createTooltipContent(
      title,
      rows
    ),
    {
      className:
        'transport-tooltip',
      direction: 'top',
      sticky: true,
      opacity: 0.96,
      offset: [0, -6],
    }
  )
}

/*
  Leaflet GeoJSON features are normally optimized
  for mouse interaction.

  This helper gives each SVG map feature:
  - Tab focus
  - role="button"
  - an accessible label
  - Enter activation
  - Space activation
*/
function makeKeyboardAccessible(
  layer,
  accessibleLabel,
  onActivate
) {
  function configureElement() {
    const element =
      layer.getElement?.()

    if (!element) {
      return
    }

    element.setAttribute(
      'tabindex',
      '0'
    )

    element.setAttribute(
      'role',
      'button'
    )

    element.setAttribute(
      'aria-label',
      accessibleLabel
    )

    element.classList.add(
      'keyboard-map-feature'
    )

    function handleKeyDown(
      event
    ) {
      if (
        event.key !== 'Enter' &&
        event.key !== ' '
      ) {
        return
      }

      event.preventDefault()
      event.stopPropagation()

      onActivate()
    }

    element.addEventListener(
      'keydown',
      handleKeyDown
    )
  }

  /*
    Depending on when Leaflet creates the SVG node,
    getElement() can initially be unavailable.

    Configure immediately when possible and also on
    the Leaflet "add" event as a safe fallback.
  */
  configureElement()

  layer.once(
    'add',
    configureElement
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
  const adaptiveLineClass =
    visibility.grid
      ? 'grid-reactive-line'
      : ''

  const adaptiveMarkerClass =
    visibility.grid
      ? 'grid-reactive-marker'
      : ''

  function selectFeature(
    type,
    feature
  ) {
    onSelect({
      type,
      properties:
        feature.properties,
      feature,
    })
  }

  return (
    <>
      {/* ================================================== */}
      {/* Analysis grid                                      */}
      {/* ================================================== */}

      <Pane
        name="analysis-grid-pane"
        style={
          ANALYSIS_PANE_STYLE
        }
      >
        {visibility.grid &&
          grid && (
            <GeoJSON
              key={
                selectedMetric
              }
              data={grid}
              renderer={GRID_RENDERER}
              style={(
                feature
              ) => ({
                color:
                  '#475569',
                weight: 0.8,
                opacity: 0.62,
                fillColor:
                  getPriorityColor(
                    feature
                      .properties[
                      selectedMetric
                    ]
                  ),
                fillOpacity: 0.42,
              })}
              onEachFeature={(
                feature,
                layer
              ) => {
                const properties =
                  feature.properties

                const activate =
                  () => {
                    selectFeature(
                      'Grid cell',
                      feature
                    )
                  }

                layer.on(
                  'mouseover',
                  (event) => {
                    if (!layer.getTooltip()) {
                      bindTooltip(
                        layer,
                        'Analysis cell',
                        [
                          `ID: ${
                            properties.id
                          }`,
                          `${
                            METRIC_LABELS[
                              selectedMetric
                            ]
                          }: ${showScore(
                            properties[
                              selectedMetric
                            ]
                          )}`,
                        ]
                      )
                    }

                    layer.openTooltip(
                      event.latlng
                    )

                    layer.setStyle({
                      weight: 1.4,
                      opacity: 0.82,
                      fillOpacity:
                        0.47,
                    })
                  }
                )

                layer.on(
                  'mouseout',
                  () => {
                    layer.closeTooltip()

                    layer.setStyle({
                      color:
                        '#475569',
                      weight: 0.8,
                      opacity: 0.62,
                      fillColor:
                        getPriorityColor(
                          properties[
                            selectedMetric
                          ]
                        ),
                      fillOpacity:
                        0.42,
                    })
                  }
                )

                layer.on(
                  'click',
                  activate
                )
              }}
            />
          )}
      </Pane>

      {/* ================================================== */}
      {/* Existing network lines                             */}
      {/* ================================================== */}

      <Pane
        name="existing-lines-pane"
        style={
          EXISTING_LINES_PANE_STYLE
        }
      >
        {visibility.busRoutes &&
          busRoutes && (
            <GeoJSON
              data={busRoutes}
              style={{
                color: '#2563eb',
                weight: 4,
                opacity: 0.8,
                lineCap: 'round',
                lineJoin: 'round',
                className:
                  adaptiveLineClass,
              }}
              onEachFeature={(
                feature,
                layer
              ) => {
                const properties =
                  feature.properties

                const activate =
                  () => {
                    selectFeature(
                      'Bus route',
                      feature
                    )
                  }

                bindTooltip(
                  layer,
                  properties.name ??
                    'Bus route',
                  [
                    `Route: ${showValue(
                      properties.route_ref
                    )}`,
                    `Route avg. daily validations: ${showValue(
                      properties.avg_daily_validations
                    )}`,
                  ]
                )

                makeKeyboardAccessible(
                  layer,
                  `Bus route ${
                    properties.name ??
                    properties.route_ref ??
                    properties.id
                  }`,
                  activate
                )

                layer.on(
                  'mouseover',
                  () => {
                    layer.setStyle({
                      weight: 6,
                      opacity: 1,
                    })
                  }
                )

                layer.on(
                  'mouseout',
                  () => {
                    layer.setStyle({
                      color:
                        '#2563eb',
                      weight: 4,
                      opacity: 0.8,
                    })
                  }
                )

                layer.on(
                  'click',
                  activate
                )
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
                opacity: 0.82,
                lineCap: 'round',
                lineJoin: 'round',
                className:
                  adaptiveLineClass,
              }}
              onEachFeature={(
                feature,
                layer
              ) => {
                const properties =
                  feature.properties

                const activate =
                  () => {
                    selectFeature(
                      'Cycleway',
                      feature
                    )
                  }

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

                makeKeyboardAccessible(
                  layer,
                  `Cycleway ${
                    properties.name ??
                    properties.id
                  }`,
                  activate
                )

                layer.on(
                  'mouseover',
                  () => {
                    layer.setStyle({
                      weight: 6,
                      opacity: 1,
                    })
                  }
                )

                layer.on(
                  'mouseout',
                  () => {
                    layer.setStyle({
                      color:
                        '#16a34a',
                      weight: 4,
                      opacity: 0.82,
                    })
                  }
                )

                layer.on(
                  'click',
                  activate
                )
              }}
            />
          )}
      </Pane>

      {/* ================================================== */}
      {/* Existing network points                            */}
      {/* ================================================== */}

      <Pane
        name="existing-points-pane"
        style={
          EXISTING_POINTS_PANE_STYLE
        }
      >
        {visibility.busStops &&
          busStops && (
            <GeoJSON
              data={busStops}
              pointToLayer={(
                feature,
                latlng
              ) =>
                L.circleMarker(
                  latlng,
                  {
                    radius: 6,
                    color:
                      '#ffffff',
                    weight: 2,
                    fillColor:
                      '#2563eb',
                    fillOpacity:
                      0.95,
                    className:
                      adaptiveMarkerClass,
                  }
                )
              }
              onEachFeature={(
                feature,
                layer
              ) => {
                const properties =
                  feature.properties

                const activate =
                  () => {
                    selectFeature(
                      'Bus stop',
                      feature
                    )
                  }

                bindTooltip(
                  layer,
                  properties.name ??
                    'Bus stop',
                  [
                    `ID: ${
                      properties.id
                    }`,
                  ]
                )

                makeKeyboardAccessible(
                  layer,
                  `Bus stop ${
                    properties.name ??
                    properties.id
                  }`,
                  activate
                )

                layer.on(
                  'mouseover',
                  () => {
                    layer.setRadius(
                      8
                    )
                  }
                )

                layer.on(
                  'mouseout',
                  () => {
                    layer.setRadius(
                      6
                    )
                  }
                )

                layer.on(
                  'click',
                  activate
                )
              }}
            />
          )}

        {visibility
          .metroStations &&
          metroStations && (
            <GeoJSON
              data={
                metroStations
              }
              pointToLayer={(
                feature,
                latlng
              ) =>
                L.circleMarker(
                  latlng,
                  {
                    radius: 8,
                    color:
                      '#0f172a',
                    weight: 3,
                    fillColor:
                      '#f8fafc',
                    fillOpacity:
                      0.96,
                    className:
                      adaptiveMarkerClass,
                  }
                )
              }
              onEachFeature={(
                feature,
                layer
              ) => {
                const properties =
                  feature.properties

                const activate =
                  () => {
                    selectFeature(
                      'Metro station',
                      feature
                    )
                  }

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

                makeKeyboardAccessible(
                  layer,
                  `Metro station ${
                    properties.name ??
                    properties.id
                  }`,
                  activate
                )

                layer.on(
                  'mouseover',
                  () => {
                    layer.setRadius(
                      10
                    )
                  }
                )

                layer.on(
                  'mouseout',
                  () => {
                    layer.setRadius(
                      8
                    )
                  }
                )

                layer.on(
                  'click',
                  activate
                )
              }}
            />
          )}
      </Pane>

      {/* ================================================== */}
      {/* Proposed interventions                              */}
      {/* ================================================== */}

      <Pane
        name="recommendations-pane"
        style={
          RECOMMENDATIONS_PANE_STYLE
        }
      >
        {visibility
          .busRecommendations &&
          busRecommendations && (
            <GeoJSON
              data={
                busRecommendations
              }
              pointToLayer={(
                feature,
                latlng
              ) =>
                L.circleMarker(
                  latlng,
                  {
                    radius: 10,
                    color:
                      '#6d28d9',
                    weight: 3,
                    fillColor:
                      '#a78bfa',
                    fillOpacity:
                      0.94,
                    className:
                      adaptiveMarkerClass,
                  }
                )
              }
              onEachFeature={(
                feature,
                layer
              ) => {
                const properties =
                  feature.properties

                const activate =
                  () => {
                    selectFeature(
                      'Bus recommendation',
                      feature
                    )
                  }

                bindTooltip(
                  layer,
                  'Candidate Bus Improvement',
                  [
                    `Priority: ${showScore(
                      properties.priority
                    )}`,
                    `Population affected: ${showValue(
                      properties.population_affected
                    )}`,
                  ]
                )

                makeKeyboardAccessible(
                  layer,
                  `Candidate Bus Improvement ${
                    properties.id
                  }. Priority ${showScore(
                    properties.priority
                  )}`,
                  activate
                )

                layer.on(
                  'mouseover',
                  () => {
                    layer.setRadius(
                      12
                    )
                  }
                )

                layer.on(
                  'mouseout',
                  () => {
                    layer.setRadius(
                      10
                    )
                  }
                )

                layer.on(
                  'click',
                  activate
                )
              }}
            />
          )}

        {visibility
          .bikeRecommendations &&
          bikeRecommendations && (
            <GeoJSON
              data={
                bikeRecommendations
              }
              style={{
                color: '#0891b2',
                weight: 6,
                opacity: 0.9,
                dashArray:
                  '10 6',
                lineCap: 'round',
                lineJoin: 'round',
                className:
                  adaptiveLineClass,
              }}
              onEachFeature={(
                feature,
                layer
              ) => {
                const properties =
                  feature.properties

                const activate =
                  () => {
                    selectFeature(
                      'Bike recommendation',
                      feature
                    )
                  }

                bindTooltip(
                  layer,
                  'Candidate Bicycle Corridor',
                  [
                    `Priority: ${showScore(
                      properties.priority
                    )}`,
                    `Length: ${showValue(
                      properties.length_m,
                      ' m'
                    )}`,
                    'Further engineering assessment',
                  ]
                )

                makeKeyboardAccessible(
                  layer,
                  `Candidate Bicycle Corridor ${
                    properties.id
                  }. Priority ${showScore(
                    properties.priority
                  )}. Further engineering assessment.`,
                  activate
                )

                layer.on(
                  'mouseover',
                  () => {
                    layer.setStyle({
                      weight: 8,
                      opacity: 1,
                    })
                  }
                )

                layer.on(
                  'mouseout',
                  () => {
                    layer.setStyle({
                      color:
                        '#0891b2',
                      weight: 6,
                      opacity: 0.9,
                      dashArray:
                        '10 6',
                    })
                  }
                )

                layer.on(
                  'click',
                  activate
                )
              }}
            />
          )}
      </Pane>
    </>
  )
}

export default memo(MapLayers)