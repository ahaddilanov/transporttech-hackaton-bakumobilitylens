import { useEffect, useState } from 'react'
import L from 'leaflet'
import { GeoJSON, MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

import { loadGeoJson } from './data/loadGeoJson'

function App() {
  const [busStops, setBusStops] = useState(null)

  useEffect(() => {
    loadGeoJson('/data/bus_stops.geojson')
      .then((data) => {
        setBusStops(data)
      })
      .catch((error) => {
        console.error(error)
      })
  }, [])

  return (
    <MapContainer
      center={[40.4093, 49.8671]}
      zoom={12}
      className="map"
    >
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {busStops && (
        <GeoJSON
          data={busStops}
          pointToLayer={(feature, latlng) =>
            L.circleMarker(latlng, {
              radius: 7,
              weight: 2,
              fillOpacity: 0.8,
            })
          }
        />
      )}
    </MapContainer>
  )
}

export default App