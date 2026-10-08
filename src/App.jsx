import { useEffect, useState } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

import DetailsPanel from './components/DetailsPanel'
import MapLayers from './components/MapLayers'
import PriorityLegend from './components/PriorityLegend'
import ScoreSelector from './components/ScoreSelector'
import SummaryPanel from './components/SummaryPanel'
import { DATA_SOURCES } from './data/dataSources'
import { loadGeoJson } from './data/loadGeoJson'

function App() {
  const [busStops, setBusStops] = useState(null)
  const [busRoutes, setBusRoutes] = useState(null)
  const [metroStations, setMetroStations] = useState(null)
  const [cycleways, setCycleways] = useState(null)
  const [grid, setGrid] = useState(null)
  const [busRecommendations, setBusRecommendations] = useState(null)
  const [bikeRecommendations, setBikeRecommendations] = useState(null)
  const [summary, setSummary] = useState(null)

  const [selectedFeature, setSelectedFeature] = useState(null)
  const [selectedMetric, setSelectedMetric] = useState('mobility_gap')

  useEffect(() => {
    loadGeoJson(DATA_SOURCES.busStops)
      .then(setBusStops)
      .catch(console.error)

    loadGeoJson(DATA_SOURCES.busRoutes)
      .then(setBusRoutes)
      .catch(console.error)

    loadGeoJson(DATA_SOURCES.metroStations)
      .then(setMetroStations)
      .catch(console.error)

    loadGeoJson(DATA_SOURCES.cycleways)
      .then(setCycleways)
      .catch(console.error)

    loadGeoJson(DATA_SOURCES.grid)
      .then(setGrid)
      .catch(console.error)

    loadGeoJson(DATA_SOURCES.busRecommendations)
      .then(setBusRecommendations)
      .catch(console.error)

    loadGeoJson(DATA_SOURCES.bikeRecommendations)
      .then(setBikeRecommendations)
      .catch(console.error)

    fetch(DATA_SOURCES.summary)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to load summary data')
        }

        return response.json()
      })
      .then(setSummary)
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

      <SummaryPanel summary={summary} />

      <DetailsPanel selectedFeature={selectedFeature} />

      <PriorityLegend selectedMetric={selectedMetric} />
    </div>
  )
}

export default App