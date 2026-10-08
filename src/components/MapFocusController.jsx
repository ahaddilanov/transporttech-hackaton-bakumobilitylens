import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'

function MapFocusController({ focusRequest }) {
  const map = useMap()

  useEffect(() => {
    const feature = focusRequest?.feature

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

    map.flyToBounds(bounds, {
      paddingTopLeft: [360, 110],
      paddingBottomRight: [360, 90],
      maxZoom: 15,
      animate: true,
      duration: 0.7,
    })
  }, [focusRequest, map])

  return null
}

export default MapFocusController