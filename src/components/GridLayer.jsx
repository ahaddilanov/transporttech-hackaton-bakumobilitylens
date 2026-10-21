import { memo, useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import ClickOnlyCanvas from './ClickOnlyCanvas'
import useMapInspection from './useMapInspection'
import { createBoundsIndex } from '../utils/boundsIndex'

function styleFor(feature, metric) {
  const score = feature.properties[metric]
  const fillColor = score == null ? '#9ca3af' : score >= 75 ? '#dc2626'
    : score >= 50 ? '#f97316' : score >= 25 ? '#eab308' : '#22c55e'
  return { color: '#475569', weight: 0.8, opacity: 0.62, fillColor, fillOpacity: 0.42 }
}

function GridLayer({ data, selectedMetric, visible, onSelect }) {
  const map = useMap()
  const canInspect = useMapInspection()
  const state = useRef(null)

  useEffect(() => {
    if (!data) return
    const renderer = new ClickOnlyCanvas({ pane: 'analysis-grid-pane' })
    // Keep all feature objects attached for the dataset's lifetime. The
    // renderer independently limits projection, drawing and clicks to the view.
    const group = L.geoJSON(data, { renderer, bubblingMouseEvents: false })
    const index = createBoundsIndex(group.getLayers(), layer => {
      const bounds = layer.getBounds()
      return [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()]
    })
    renderer.setBoundsIndex(index)
    state.current = { group }
    group.on('click', event => {
      if (!canInspect()) return
      const feature = event.layer.feature
      onSelect({ type: 'Grid cell', properties: feature.properties, feature })
    })
    return () => {
      group.off()
      group.remove()
      renderer.remove()
      state.current = null
    }
  }, [data, map, onSelect, canInspect])

  useEffect(() => {
    state.current?.group.setStyle(feature => styleFor(feature, selectedMetric))
  }, [data, map, onSelect, canInspect, selectedMetric])

  useEffect(() => {
    const current = state.current
    if (!current) return
    if (visible) current.group.addTo(map)
    else current.group.remove()
  }, [data, map, onSelect, canInspect, visible])
  return null
}

export default memo(GridLayer)
