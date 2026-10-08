import { useEffect, useState } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

import DetailsPanel from './components/DetailsPanel'
import MapLayers from './components/MapLayers'
import PriorityLegend from './components/PriorityLegend'
import ScoreSelector from './components/ScoreSelector'
import { loadGeoJson } from './data/loadGeoJson'

function App() {
  const [busStops, setBusStops] = useState(null)
  const [busRoutes, setBusRoutes] = useState(null)
  const [metroStations, setMetroStations] = useState(null)
  const [cycleways, setCycleways] = useState(null)
  const [grid, setGrid] = useState(null)
  const [busRecommendations, setBusRecommendations] = useState(null)
  const [bikeRecommendations, setBikeRecommendations] = useState(null)

  const [selectedFeature, setSelectedFeature] = useState(null)
  const [selectedMetric, setSelectedMetric] = useState('mobility_gap')

  useEffect(() => {
    loadGeoJson('/data/bus_stops.geojson')
      .then(setBusStops)
      .catch(console.error)

    loadGeoJson('/data/bus_routes.geojson')
      .then(setBusRoutes)
      .catch(console.error)

    loadGeoJson('/data/metro_stations.geojson')
      .then(setMetroStations)
      .catch(console.error)

    loadGeoJson('/data/cycleways.geojson')
      .then(setCycleways)
      .catch(console.error)

    loadGeoJson('/data/grid.geojson')
      .then(setGrid)
      .catch(console.error)

    loadGeoJson('/data/bus_recommendations.geojson')
      .then(setBusRecommendations)
      .catch(console.error)

    loadGeoJson('/data/bike_recommendations.geojson')
      .then(setBikeRecommendations)
      .catch(console.error)
  }, [])

  return (
    <div className="app">
      <MapContainer
        center={[40.4093, 49.8671]}
        zoom={12}
        className="map"
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapLayers
          busStops={busStops}
          busRoutes={busRoutes}
          metroStations={metroStations}
          cycleways={cycleways}
          grid={grid}
          busRecommendations={busRecommendations}
          bikeRecommendations={bikeRecommendations}
          selectedMetric={selectedMetric}
          onSelect={setSelectedFeature}
        />
      </MapContainer>

      <ScoreSelector
        selectedMetric={selectedMetric}
        onChange={setSelectedMetric}
      />

      <DetailsPanel selectedFeature={selectedFeature} />

      <PriorityLegend selectedMetric={selectedMetric} />
    </div>
  )
}

export default App