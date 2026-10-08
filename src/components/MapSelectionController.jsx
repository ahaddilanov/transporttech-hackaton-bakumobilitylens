import { useEffect } from 'react'
import { useMapEvents } from 'react-leaflet'

function MapSelectionController({ onClearSelection }) {
  useMapEvents({
    click(event) {
      const target = event.originalEvent?.target

      if (
        target instanceof Element &&
        target.closest('.leaflet-interactive')
      ) {
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