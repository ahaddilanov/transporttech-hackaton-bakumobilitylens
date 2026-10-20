import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'

const BAKU_CENTER = [40.4093, 49.8671]
const BAKU_ZOOM = 12

function MapFocusController({ focusRequest }) {
  const map = useMap()

  useEffect(() => {
    if (!focusRequest) {
      return
    }

    if (focusRequest.type === 'overview') {
      map.flyTo(BAKU_CENTER, BAKU_ZOOM, {
        animate: true,
        duration: 0.7,
      })

      return
    }

    const feature = focusRequest.feature

    if (!feature?.geometry) {
      return
    }

    const featureLayer = L.geoJSON(feature)
    const geometryType = feature.geometry.type

    if (geometryType === 'Point') {
      const layer = featureLayer.getLayers()[0]

      if (!layer?.getLatLng) {
        return
      }

      const latlng = layer.getLatLng()
      const targetZoom = Math.max(map.getZoom(), 15)

      map.flyTo(latlng, targetZoom, {
        animate: true,
        duration: 0.6,
      })

      return
    }

    const bounds = featureLayer.getBounds()

    if (!bounds.isValid()) {
      return
    }

    const compact = map.getSize().x <= 1100
    map.flyToBounds(bounds, {
      paddingTopLeft: compact ? [24, 24] : [360, 110],
      paddingBottomRight: compact ? [24, 24] : [360, 90],
      maxZoom: 15,
      animate: true,
      duration: 0.7,
    })
  }, [focusRequest, map])

  return null
}

export default MapFocusController