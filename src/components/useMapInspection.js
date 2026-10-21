import { useCallback, useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

// Mutable motion flags avoid React renders for every map movement. Keyboard and
// ranking activation remain explicit actions and do not use this mouse gate.
export default function useMapInspection() {
  const map = useMap()
  const motion = useRef({ moving: false, zooming: false })
  useEffect(() => {
    const events = {
      movestart() { motion.current.moving = true },
      moveend() { motion.current.moving = false },
      zoomstart() { motion.current.zooming = true },
      zoomend() { motion.current.zooming = false },
    }
    map.on(events)
    return () => map.off(events)
  }, [map])
  return useCallback(() => !motion.current.moving && !motion.current.zooming && !map.dragging.moving(), [map])
}
