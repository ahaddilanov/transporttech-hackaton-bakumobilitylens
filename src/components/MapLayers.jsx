import useMapInspection from './useMapInspection'
import GridLayer from './GridLayer'
import { showScore } from '../utils/presentation'
import { memo } from 'react'
import L from 'leaflet'
import {
  GeoJSON,
  Pane,
} from 'react-leaflet'

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
  let element
  function handleKeyDown(event) {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    event.stopPropagation()
    onActivate()
  }
  function cleanupElement() {
    element?.removeEventListener('keydown', handleKeyDown)
    element = null
  }
  function configureElement() {
    cleanupElement()
    element = layer.getElement?.()
    if (!element) return
    element.setAttribute('tabindex', '0')
    element.setAttribute('role', 'button')
    element.setAttribute('aria-label', accessibleLabel)
    element.classList.add('keyboard-map-feature')
    element.addEventListener('keydown', handleKeyDown)
  }
  configureElement()
  layer.on({ add: configureElement, remove: cleanupElement })
}

const TransportLayers = memo(function TransportLayers({
  busStops,
  busRoutes,
  metroStations,
  cycleways,
  busRecommendations,
  bikeRecommendations,
  visibility,
  onSelect,
  labels,
}) {
  const canInspect = useMapInspection()
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
                  'click',
                  () => { if (canInspect()) activate() }
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

                makeKeyboardAccessible(
                  layer,
                  `Cycleway ${
                    properties.name ??
                    properties.id
                  }`,
                  activate
                )

                layer.on(
                  'click',
                  () => { if (canInspect()) activate() }
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

                makeKeyboardAccessible(
                  layer,
                  `Bus stop ${
                    properties.name ??
                    properties.id
                  }`,
                  activate
                )

                layer.on(
                  'click',
                  () => { if (canInspect()) activate() }
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

                makeKeyboardAccessible(
                  layer,
                  `Metro station ${
                    properties.name ??
                    properties.id
                  }`,
                  activate
                )

                layer.on(
                  'click',
                  () => { if (canInspect()) activate() }
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

                makeKeyboardAccessible(
                  layer,
                  `${labels.get(properties.id) ?? 'Candidate Bus Stop'}. Priority ${showScore(
                    properties.priority
                  )}`,
                  activate
                )

                layer.on(
                  'click',
                  () => { if (canInspect()) activate() }
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

                makeKeyboardAccessible(
                  layer,
                  `${labels.get(properties.id) ?? 'Bicycle Corridor'}. Priority ${showScore(
                    properties.priority
                  )}. Further engineering assessment.`,
                  activate
                )

                layer.on(
                  'click',
                  () => { if (canInspect()) activate() }
                )
              }}
            />
          )}
      </Pane>
    </>
  )
})

function MapLayers({ grid, selectedMetric, ...transportProps }) {
  return (
    <>
      <Pane name="analysis-grid-pane" style={ANALYSIS_PANE_STYLE}>
        <GridLayer data={grid} selectedMetric={selectedMetric}
          visible={transportProps.visibility.grid} onSelect={transportProps.onSelect} />
      </Pane>
      <TransportLayers {...transportProps} />
    </>
  )
}

export default memo(MapLayers)