import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

function App() {
  return (
    <MapContainer
      center={[40.4093, 49.8671]}
      zoom={12}
      className="map"
    >
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
    </MapContainer>
  )
}

export default App