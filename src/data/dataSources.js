const IS_DEMO = import.meta.env.MODE === 'demo'
const API_BASE_URL = (IS_DEMO ? '' : import.meta.env.VITE_API_BASE_URL ?? '')
  .trim()
  .replace(/\/+$/, '')

const STATIC_SOURCES = {
  busStops: '/data/bus_stops.geojson',
  busRoutes: '/data/bus_routes.geojson',
  metroStations: '/data/metro_stations.geojson',
  cycleways: '/data/cycleways.geojson',
  grid: '/data/grid.geojson',
  busRecommendations: '/data/bus_recommendations.geojson',
  bikeRecommendations: '/data/bike_recommendations.geojson',
  summary: '/data/summary.json',
  interventionScenarios: '/data/intervention_scenarios.json',
}

const API_SOURCES = {
  // Saved simulations remain a static snapshot; no API endpoint is assumed.
  interventionScenarios: STATIC_SOURCES.interventionScenarios,
  busStops: `${API_BASE_URL}/api/v1/bus-stops`,
  busRoutes: `${API_BASE_URL}/api/v1/bus-routes`,
  metroStations: `${API_BASE_URL}/api/v1/metro-stations`,
  cycleways: `${API_BASE_URL}/api/v1/cycleways`,
  grid: `${API_BASE_URL}/api/v1/grid`,
  busRecommendations: `${API_BASE_URL}/api/v1/recommendations/bus`,
  bikeRecommendations: `${API_BASE_URL}/api/v1/recommendations/bike`,
  summary: `${API_BASE_URL}/api/v1/summary`,
}

export const DATA_MODE = IS_DEMO ? 'demo' : API_BASE_URL ? 'api' : 'static'

export const DATA_SOURCES =
  DATA_MODE === 'api' ? API_SOURCES : STATIC_SOURCES
