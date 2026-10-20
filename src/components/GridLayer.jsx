import { memo, useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import { showScore } from '../utils/presentation'

const METRIC_LABELS = {
  mobility_gap: 'Mobility gap', bus_priority: 'Bus priority', bike_priority: 'Bike priority',
}

function styleFor(feature, metric) {
  const score = feature.properties[metric]
  const fillColor = score == null ? '#9ca3af' : score >= 75 ? '#dc2626'
    : score >= 50 ? '#f97316' : score >= 25 ? '#eab308' : '#22c55e'
  return { color: '#475569', weight: 0.8, opacity: 0.62, fillColor, fillOpacity: 0.42 }
}

function tooltipContent(feature, metric) {
  const content = document.createElement('div')
  content.className = 'transport-tooltip-content'
  const title = document.createElement('strong')
  title.textContent = `Analysis cell ${feature.properties.id}`
  const score = document.createElement('span')
  score.textContent = `${METRIC_LABELS[metric]}: ${showScore(feature.properties[metric])}`
  content.append(title, score)
  return content
}

function GridLayer({ data, selectedMetric, visible, onSelect }) {
  const map = useMap()
  const state = useRef(null)

  // Geometry and shared handlers live for the dataset's lifetime, not the metric's.
  useEffect(() => {
    if (!data) return
    const renderer = L.canvas({ pane: 'analysis-grid-pane' })
    const group = L.geoJSON(data, { renderer, bubblingMouseEvents: false })
    const tooltip = L.tooltip({ className: 'transport-tooltip', direction: 'top', offset: [0, -6] })
    const current = { group, renderer, tooltip, metric: 'mobility_gap', hovered: null }
    state.current = current
    group.on({
      mouseover(event) {
        const layer = event.layer
        current.hovered = layer
        layer.setStyle({ weight: 1.4, opacity: 0.82, fillOpacity: 0.47 })
        tooltip.setContent(tooltipContent(layer.feature, current.metric)).setLatLng(event.latlng).addTo(map)
      },
      mousemove(event) { tooltip.setLatLng(event.latlng) },
      mouseout(event) {
        event.layer.setStyle(styleFor(event.layer.feature, current.metric))
        current.hovered = null
        tooltip.remove()
      },
      click(event) {
        const feature = event.layer.feature
        onSelect({ type: 'Grid cell', properties: feature.properties, feature })
      },
    })
    return () => {
      group.off()
      group.remove()
      tooltip.remove()
      renderer.remove()
      state.current = null
    }
  }, [data, map, onSelect])

  useEffect(() => {
    const current = state.current
    if (!current) return
    current.metric = selectedMetric
    current.group.setStyle(feature => styleFor(feature, selectedMetric))
    if (current.hovered) {
      current.hovered.setStyle({ weight: 1.4, opacity: 0.82, fillOpacity: 0.47 })
      current.tooltip.setContent(tooltipContent(current.hovered.feature, selectedMetric))
    }
  }, [data, map, onSelect, selectedMetric])

  useEffect(() => {
    const current = state.current
    if (!current) return
    if (visible) current.group.addTo(map)
    else {
      current.tooltip.remove()
      if (current.hovered) current.hovered.setStyle(styleFor(current.hovered.feature, current.metric))
      current.hovered = null
      current.group.remove()
    }
  }, [data, map, onSelect, visible])
  return null
}

export default memo(GridLayer)
