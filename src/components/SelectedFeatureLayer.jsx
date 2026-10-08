import L from 'leaflet'
import { GeoJSON } from 'react-leaflet'

function SelectedFeatureLayer({ selectedFeature }) {
  if (!selectedFeature?.feature) {
    return null
  }

  const geometryType = selectedFeature.feature.geometry?.type

  if (geometryType === 'Point') {
    return (
      <GeoJSON
        key={`${selectedFeature.type}-${selectedFeature.properties.id}`}
        data={selectedFeature.feature}
        pointToLayer={(feature, latlng) =>
          L.circleMarker(latlng, {
            radius: 14,
            color: '#111827',
            weight: 4,
            fillColor: '#ffffff',
            fillOpacity: 0.35,
          })
        }
        interactive={false}
      />
    )
  }

  if (
    geometryType === 'LineString' ||
    geometryType === 'MultiLineString'
  ) {
    return (
      <GeoJSON
        key={`${selectedFeature.type}-${selectedFeature.properties.id}`}
        data={selectedFeature.feature}
        style={{
          color: '#111827',
          weight: 10,
          opacity: 0.4,
        }}
        interactive={false}
      />
    )
  }

  if (
    geometryType === 'Polygon' ||
    geometryType === 'MultiPolygon'
  ) {
    return (
      <GeoJSON
        key={`${selectedFeature.type}-${selectedFeature.properties.id}`}
        data={selectedFeature.feature}
        style={{
          color: '#111827',
          weight: 4,
          fillColor: '#ffffff',
          fillOpacity: 0.08,
        }}
        interactive={false}
      />
    )
  }

  return null
}

export default SelectedFeatureLayer