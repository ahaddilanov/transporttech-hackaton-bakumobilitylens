import { useEffect, useState } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

import AnalysisPanel from './components/AnalysisPanel'
import AppHeader from './components/AppHeader'
import DataStatus from './components/DataStatus'
import DetailsPanel from './components/DetailsPanel'
import LayerPanel from './components/LayerPanel'
import MapFocusController from './components/MapFocusController'
import MapLayers from './components/MapLayers'
import PriorityRanking from './components/PriorityRanking'
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

const INITIAL_LAYER_VISIBILITY = {
  busStops: true,
  busRoutes: true,
  metroStations: true,
  cycleways: true,
  grid: true,
  busRecommendations: true,
  bikeRecommendations: true,
}

const FEATURE_LAYER_MAP = {
  'Bus stop': 'busStops',
  'Bus route': 'busRoutes',
  'Metro station': 'metroStations',
  Cycleway: 'cycleways',
  'Grid cell': 'grid',
  'Bus recommendation': 'busRecommendations',
  'Bike recommendation': 'bikeRecommendations',
}

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

  const [focusRequest, setFocusRequest] =
    useState(null)

  const [layerVisibility, setLayerVisibility] =
    useState(INITIAL_LAYER_VISIBILITY)

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
    const layerKey =
      FEATURE_LAYER_MAP[selection.type]

    if (layerKey) {
      setLayerVisibility((current) => ({
        ...current,
        [layerKey]: true,
      }))
    }

    setSelectedFeature(selection)

    if (
      selection.focusMap &&
      selection.feature
    ) {
      setFocusRequest((currentRequest) => ({
        feature: selection.feature,
        sequence:
          (currentRequest?.sequence ?? 0) + 1,
      }))
    }
  }

  function handleLayerToggle(layerKey) {
    setLayerVisibility((current) => {
      const nextVisible = !current[layerKey]

      if (
        !nextVisible &&
        selectedFeature &&
        FEATURE_LAYER_MAP[
          selectedFeature.type
        ] === layerKey
      ) {
        setSelectedFeature(null)
      }

      return {
        ...current,
        [layerKey]: nextVisible,
      }
    })
  }

  return (
    <div
      className="app"
      data-theme={theme}
    >
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
          visibility={layerVisibility}
          onSelect={setSelectedFeature}
        />

        <SelectedFeatureLayer
          selectedFeature={selectedFeature}
        />

        <MapFocusController
          focusRequest={focusRequest}
        />
      </MapContainer>

      <SummaryPanel summary={summary} />

      <PriorityRanking
        busRecommendations={busRecommendations}
        bikeRecommendations={bikeRecommendations}
        selectedFeature={selectedFeature}
        onSelect={handleRankingSelect}
      />

      <DetailsPanel
        selectedFeature={selectedFeature}
      />

      <AnalysisPanel
        selectedMetric={selectedMetric}
        onChange={setSelectedMetric}
      />

      <LayerPanel
        visibility={layerVisibility}
        onToggle={handleLayerToggle}
      />

      <DataStatus
        loading={loading}
        errors={loadErrors}
      />
    </div>
  )
}

export default App