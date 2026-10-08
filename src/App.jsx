import { useEffect, useState } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

import AppHeader from './components/AppHeader'
import DataStatus from './components/DataStatus'
import DetailsPanel from './components/DetailsPanel'
import MapFocusController from './components/MapFocusController'
import MapLayers from './components/MapLayers'
import PriorityLegend from './components/PriorityLegend'
import PriorityRanking from './components/PriorityRanking'
import ScoreSelector from './components/ScoreSelector'
import SelectedFeatureLayer from './components/SelectedFeatureLayer'
import SummaryPanel from './components/SummaryPanel'
import { DATA_SOURCES } from './data/dataSources'
import { loadGeoJson, loadJson } from './data/loadGeoJson'
import {
  validateBikeRecommendations,
  validateBusRecommendations,
  validateBusRoutes,
  validateBusStops,
  validateCycleways,
  validateGrid,
  validateMetroStations,
  validateSummary,
} from './data/validateData'

function App() {
  const [busStops, setBusStops] = useState(null)
  const [busRoutes, setBusRoutes] = useState(null)
  const [metroStations, setMetroStations] = useState(null)
  const [cycleways, setCycleways] = useState(null)
  const [grid, setGrid] = useState(null)
  const [busRecommendations, setBusRecommendations] =
    useState(null)
  const [bikeRecommendations, setBikeRecommendations] =
    useState(null)
  const [summary, setSummary] = useState(null)

  const [selectedFeature, setSelectedFeature] =
    useState(null)
  const [selectedMetric, setSelectedMetric] =
    useState('mobility_gap')
  const [theme, setTheme] = useState('light')
  const [focusRequest, setFocusRequest] = useState(null)

  const [loading, setLoading] = useState(true)
  const [loadErrors, setLoadErrors] = useState([])

  useEffect(() => {
    let cancelled = false

    async function loadDataset(
      label,
      loader,
      source,
      validator,
      setter
    ) {
      try {
        const data = await loader(source)
        const validatedData = validator(data)

        if (!cancelled) {
          setter(validatedData)
        }
      } catch (error) {
        console.error(error)

        if (!cancelled) {
          setLoadErrors((currentErrors) => [
            ...currentErrors,
            `${label}: ${error.message}`,
          ])
        }
      }
    }

    async function loadAllData() {
      setLoading(true)
      setLoadErrors([])

      await Promise.all([
        loadDataset(
          'Bus stops',
          loadGeoJson,
          DATA_SOURCES.busStops,
          validateBusStops,
          setBusStops
        ),
        loadDataset(
          'Bus routes',
          loadGeoJson,
          DATA_SOURCES.busRoutes,
          validateBusRoutes,
          setBusRoutes
        ),
        loadDataset(
          'Metro stations',
          loadGeoJson,
          DATA_SOURCES.metroStations,
          validateMetroStations,
          setMetroStations
        ),
        loadDataset(
          'Cycleways',
          loadGeoJson,
          DATA_SOURCES.cycleways,
          validateCycleways,
          setCycleways
        ),
        loadDataset(
          'Analysis grid',
          loadGeoJson,
          DATA_SOURCES.grid,
          validateGrid,
          setGrid
        ),
        loadDataset(
          'Bus recommendations',
          loadGeoJson,
          DATA_SOURCES.busRecommendations,
          validateBusRecommendations,
          setBusRecommendations
        ),
        loadDataset(
          'Bike recommendations',
          loadGeoJson,
          DATA_SOURCES.bikeRecommendations,
          validateBikeRecommendations,
          setBikeRecommendations
        ),
        loadDataset(
          'Summary',
          loadJson,
          DATA_SOURCES.summary,
          validateSummary,
          setSummary
        ),
      ])

      if (!cancelled) {
        setLoading(false)
      }
    }

    loadAllData()

    return () => {
      cancelled = true
    }
  }, [])

  function handleRankingSelect(selection) {
    setSelectedFeature(selection)

    if (selection.focusMap && selection.feature) {
      setFocusRequest((currentRequest) => ({
        feature: selection.feature,
        sequence:
          (currentRequest?.sequence ?? 0) + 1,
      }))
    }
  }

  return (
    <div className="app" data-theme={theme}>
      <AppHeader
        theme={theme}
        onToggleTheme={() =>
          setTheme((currentTheme) =>
            currentTheme === 'light'
              ? 'dark'
              : 'light'
          )
        }
      />

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

        <SelectedFeatureLayer
          selectedFeature={selectedFeature}
        />

        <MapFocusController
          focusRequest={focusRequest}
        />
      </MapContainer>

      <ScoreSelector
        selectedMetric={selectedMetric}
        onChange={setSelectedMetric}
      />

      <SummaryPanel summary={summary} />

      <PriorityRanking
        busRecommendations={busRecommendations}
        bikeRecommendations={bikeRecommendations}
        selectedFeature={selectedFeature}
        onSelect={handleRankingSelect}
      />

      <DetailsPanel
        selectedFeature={selectedFeature}
        onClose={() => setSelectedFeature(null)}
      />

      <PriorityLegend
        selectedMetric={selectedMetric}
      />

      <DataStatus
        loading={loading}
        errors={loadErrors}
      />
    </div>
  )
}

export default App