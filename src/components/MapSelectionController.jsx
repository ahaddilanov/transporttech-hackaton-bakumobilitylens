import { useEffect } from 'react'
import { useMapEvents } from 'react-leaflet'

function MapSelectionController({ onClearSelection }) {
  useMapEvents({
    click(event) {
      const target = event.originalEvent?.target

      const interactive = target instanceof Element
        ? target.closest('.leaflet-interactive')
        : null

      // Grid feature clicks stop at their Canvas layer. A Canvas click that
      // reaches the map is empty space, even if its hover class is still set.
      if (interactive && interactive.tagName.toLowerCase() !== 'canvas') {
        return
      }

      onClearSelection()
    },
  })

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        onClearSelection()
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener(
        'keydown',
        handleKeyDown
      )
    }
  }, [onClearSelection])

  return null
}

export default MapSelectionController