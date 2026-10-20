import { recommendationLabels } from './utils/presentation'
import {
  useCallback,
  useMemo,
  useEffect,
  useState,
} from 'react'
import {
  MapContainer,
  TileLayer,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

import AnalysisPanel from './components/AnalysisPanel'
import AppHeader from './components/AppHeader'
import DataStatus from './components/DataStatus'
import DetailsPanel from './components/DetailsPanel'
import LayerPanel from './components/LayerPanel'
import MapFocusController from './components/MapFocusController'
import MapLayers from './components/MapLayers'
import MapSelectionController from './components/MapSelectionController'
import PriorityRanking from './components/PriorityRanking'
import SelectedFeatureLayer from './components/SelectedFeatureLayer'
import SummaryPanel from './components/SummaryPanel'

import {
  DATA_MODE,
  DATA_SOURCES,
} from './data/dataSources'

import {
  loadGeoJson,
  loadJson,
} from './data/loadGeoJson'

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

import {
  applyQaScenario,
} from './data/applyQaScenario'

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
  'Bus recommendation':
    'busRecommendations',
  'Bike recommendation':
    'bikeRecommendations',
}

function App() {
  const [busStops, setBusStops] =
    useState(null)

  const [busRoutes, setBusRoutes] =
    useState(null)

  const [
    metroStations,
    setMetroStations,
  ] = useState(null)

  const [cycleways, setCycleways] =
    useState(null)

  const [grid, setGrid] =
    useState(null)

  const [
    busRecommendations,
    setBusRecommendations,
  ] = useState(null)

  const [
    bikeRecommendations,
    setBikeRecommendations,
  ] = useState(null)

  const labels = useMemo(() => recommendationLabels(busRecommendations, bikeRecommendations), [busRecommendations, bikeRecommendations])

  const [summary, setSummary] =
    useState(null)

  const [
    selectedFeature,
    setSelectedFeature,
  ] = useState(null)

  const [
    selectedMetric,
    setSelectedMetric,
  ] = useState(
    'mobility_gap'
  )

  const [theme, setTheme] =
    useState('light')

  const [focusMode, setFocusMode] =
    useState(false)

  const [
    inspectorCollapsed,
    setInspectorCollapsed,
  ] = useState(true)

  const [
    focusRequest,
    setFocusRequest,
  ] = useState(null)

  const [
    layerVisibility,
    setLayerVisibility,
  ] = useState(
    INITIAL_LAYER_VISIBILITY
  )

  const [loading, setLoading] =
    useState(true)

  const [
    loadErrors,
    setLoadErrors,
  ] = useState([])

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
        const loadedData =
          await loader(source)

        /*
          Validate the real input first.

          QA transformations happen only after
          valid contract-compliant data has
          been loaded.
        */

        const validatedData =
          validator(loadedData)

        const qaData =
          applyQaScenario(
            label,
            validatedData
          )

        if (!cancelled) {
          setter(qaData)
        }
      } catch (error) {
        console.error(error)

        if (!cancelled) {
          setLoadErrors(
            (
              currentErrors
            ) => [
              ...currentErrors,
              `${label}: ${error.message}`,
            ]
          )
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
          DATA_SOURCES
            .metroStations,
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
          DATA_SOURCES
            .busRecommendations,
          validateBusRecommendations,
          setBusRecommendations
        ),

        loadDataset(
          'Bike recommendations',
          loadGeoJson,
          DATA_SOURCES
            .bikeRecommendations,
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

  const handleClearSelection =
    useCallback(() => {
      setSelectedFeature(null)
      setInspectorCollapsed(true)
    }, [])

  const handleMapSelect =
    useCallback(
      (selection) => {
        setSelectedFeature(
          selection
        )

        setInspectorCollapsed(
          false
        )
      },
      []
    )

  const handleRankingSelect =
    useCallback(
      (selection) => {
        const layerKey =
          FEATURE_LAYER_MAP[
            selection.type
          ]

        if (layerKey) {
          setLayerVisibility(
            (current) => ({
              ...current,
              [layerKey]:
                true,
            })
          )
        }

        setSelectedFeature(
          selection
        )

        setInspectorCollapsed(
          false
        )

        if (
          selection.focusMap &&
          selection.feature
        ) {
          setFocusRequest(
            (
              currentRequest
            ) => ({
              type: 'feature',

              feature:
                selection.feature,

              sequence:
                (currentRequest
                  ?.sequence ??
                  0) + 1,
            })
          )
        }
      },
      []
    )

  const handleLayerToggle =
    useCallback(
      (layerKey) => {
        setLayerVisibility(
          (current) => {
            const nextVisible =
              !current[layerKey]

            const selectedLayerKey =
              selectedFeature
                ? FEATURE_LAYER_MAP[
                    selectedFeature
                      .type
                  ]
                : null

            if (
              !nextVisible &&
              selectedLayerKey ===
                layerKey
            ) {
              setSelectedFeature(
                null
              )

              setInspectorCollapsed(
                true
              )
            }

            return {
              ...current,
              [layerKey]:
                nextVisible,
            }
          }
        )
      },
      [selectedFeature]
    )

  const handleResetView =
    useCallback(() => {
      setFocusRequest(
        (
          currentRequest
        ) => ({
          type: 'overview',

          sequence:
            (currentRequest
              ?.sequence ??
              0) + 1,
        })
      )
    }, [])

  const handleToggleTheme =
    useCallback(() => {
      setTheme(
        (currentTheme) =>
          currentTheme ===
          'light'
            ? 'dark'
            : 'light'
      )
    }, [])

  const handleToggleFocusMode =
    useCallback(() => {
      setFocusMode(
        (current) =>
          !current
      )
    }, [])

  return (
    <div
      className="app"
      data-theme={theme}
      data-focus-mode={
        focusMode
      }
    >
      <a className="skip-link" href="#analysis-controls">Skip map to analysis controls</a>
      <a className="skip-link" href="#intervention-priorities">Skip map to recommendations</a>
      <AppHeader
        theme={theme}
        onToggleTheme={
          handleToggleTheme
        }
        focusMode={
          focusMode
        }
        onToggleFocusMode={
          handleToggleFocusMode
        }
        onResetView={
          handleResetView
        }
        dataMode={
          DATA_MODE
        }
      />

      <MapContainer
        center={[
          40.4093,
          49.8671,
        ]}
        zoom={12}
        className="map"
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapLayers
          labels={labels}
          busStops={
            busStops
          }
          busRoutes={
            busRoutes
          }
          metroStations={
            metroStations
          }
          cycleways={
            cycleways
          }
          grid={grid}
          busRecommendations={
            busRecommendations
          }
          bikeRecommendations={
            bikeRecommendations
          }
          selectedMetric={
            selectedMetric
          }
          visibility={
            layerVisibility
          }
          onSelect={
            handleMapSelect
          }
        />

        <SelectedFeatureLayer
          selectedFeature={
            selectedFeature
          }
        />

        <MapFocusController
          focusRequest={
            focusRequest
          }
        />

        <MapSelectionController
          onClearSelection={
            handleClearSelection
          }
        />
      </MapContainer>

      <SummaryPanel
        summary={
          summary
        }
      />

      <PriorityRanking
        labels={labels}
        busRecommendations={
          busRecommendations
        }
        bikeRecommendations={
          bikeRecommendations
        }
        selectedFeature={
          selectedFeature
        }
        onSelect={
          handleRankingSelect
        }
      />

      <DetailsPanel
        labels={labels}
        selectedFeature={
          selectedFeature
        }
        collapsed={
          inspectorCollapsed
        }
        onCollapse={() =>
          setInspectorCollapsed(
            true
          )
        }
        onOpen={() =>
          setInspectorCollapsed(
            false
          )
        }
      />

      <AnalysisPanel
        grid={grid}
        onSelect={handleRankingSelect}
        selectedMetric={
          selectedMetric
        }
        onChange={
          setSelectedMetric
        }
      />

      <LayerPanel
        visibility={
          layerVisibility
        }
        onToggle={
          handleLayerToggle
        }
      />

      <DataStatus
        loading={
          loading
        }
        errors={
          loadErrors
        }
      />
    </div>
  )
}

export default App