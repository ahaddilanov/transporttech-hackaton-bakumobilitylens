import L from 'leaflet'
import {
  GeoJSON,
  Pane,
} from 'react-leaflet'

const SELECTION_PANE_STYLE = {
  zIndex: 450,
  pointerEvents: 'none',
}

function getOuterStyle(feature) {
  const geometryType =
    feature?.geometry?.type

  if (
    geometryType === 'Polygon' ||
    geometryType === 'MultiPolygon'
  ) {
    return {
      color: '#ffffff',
      weight: 7,
      opacity: 0.96,

      fillColor: '#0ea5e9',
      fillOpacity: 0.05,

      lineCap: 'round',
      lineJoin: 'round',
    }
  }

  return {
    color: '#ffffff',
    weight: 12,
    opacity: 0.94,

    fillOpacity: 0,

    lineCap: 'round',
    lineJoin: 'round',
  }
}

function getInnerStyle(feature) {
  const geometryType =
    feature?.geometry?.type

  if (
    geometryType === 'Polygon' ||
    geometryType === 'MultiPolygon'
  ) {
    return {
      color: '#0ea5e9',
      weight: 3,
      opacity: 1,

      fillColor: '#0ea5e9',
      fillOpacity: 0.08,

      lineCap: 'round',
      lineJoin: 'round',
    }
  }

  return {
    color: '#0ea5e9',
    weight: 6,
    opacity: 1,

    fillOpacity: 0,

    lineCap: 'round',
    lineJoin: 'round',
  }
}

function createOuterPoint(
  feature,
  latlng
) {
  return L.circleMarker(
    latlng,
    {
      radius: 15,

      color: '#ffffff',
      weight: 7,
      opacity: 0.96,

      fillColor: '#ffffff',
      fillOpacity: 0.06,

      interactive: false,
    }
  )
}

function createInnerPoint(
  feature,
  latlng
) {
  return L.circleMarker(
    latlng,
    {
      radius: 12,

      color: '#0ea5e9',
      weight: 3,
      opacity: 1,

      fillColor: '#0ea5e9',
      fillOpacity: 0.14,

      interactive: false,
    }
  )
}

function SelectedFeatureLayer({
  selectedFeature,
}) {
  const feature =
    selectedFeature?.feature

  if (!feature) {
    return null
  }

  const selectionKey = `${
    selectedFeature.type ??
    'feature'
  }-${
    selectedFeature
      .properties?.id ??
    'selected'
  }`

  return (
    <Pane
      name="selection-pane"
      style={
        SELECTION_PANE_STYLE
      }
    >
      {/* White outer halo keeps selection visible
          over both light and dark map content. */}

      <GeoJSON
        key={`${selectionKey}-outer`}
        data={feature}
        interactive={false}
        style={getOuterStyle}
        pointToLayer={
          createOuterPoint
        }
      />

      {/* Cyan inner line communicates selection
          without reusing a transport-semantic color. */}

      <GeoJSON
        key={`${selectionKey}-inner`}
        data={feature}
        interactive={false}
        style={getInnerStyle}
        pointToLayer={
          createInnerPoint
        }
      />
    </Pane>
  )
}

export default SelectedFeatureLayer