const EMPTY_FEATURE_COLLECTION = {
  type: 'FeatureCollection',
  features: [],
}

function clone(value) {
  return structuredClone(value)
}

function createEmptyData(label, data) {
  if (label === 'Summary') {
    return {
      ...data,
      grid_cells: 0,
      population_estimate: null,
      high_bus_priority_cells: 0,
      high_bike_priority_cells: 0,
    }
  }

  if (
    data?.type === 'FeatureCollection'
  ) {
    return clone(
      EMPTY_FEATURE_COLLECTION
    )
  }

  return data
}

function nullGridProperties(properties) {
  return {
    ...properties,
    population: null,
    nearest_bus_stop_m: null,
    nearest_metro_m: null,
    nearest_cycleway_m: null,
    bus_stops_500m: null,
    bus_routes_nearby: null,
    pois_nearby: null,
    bus_priority: null,
    bike_priority: null,
    mobility_gap: null,
  }
}

function nullBusStopProperties(
  properties
) {
  return {
    ...properties,
    name: null,
  }
}

function nullBusRouteProperties(
  properties
) {
  return {
    ...properties,
    name: null,
    route_ref: null,
    avg_daily_validations: null,
  }
}

function nullMetroProperties(
  properties
) {
  return {
    ...properties,
    name: null,
    avg_daily_entries: null,
  }
}

function nullCyclewayProperties(
  properties
) {
  return {
    ...properties,
    name: null,
    length_m: null,
  }
}

function nullBusRecommendationProperties(
  properties
) {
  return {
    ...properties,

    /*
      priority stays unchanged because it is
      required by the shared contract.
    */

    population_affected: null,
    current_access_m: null,
    new_access_m: null,
    access_improvement_m: null,
  }
}

function nullBikeRecommendationProperties(
  properties
) {
  return {
    ...properties,

    /*
      priority stays unchanged because it is
      required by the shared contract.
    */

    length_m: null,
    population_coverage_gain: null,
    start_name: null,
    end_name: null,
  }
}

function transformFeatureCollection(
  data,
  transformProperties
) {
  if (
    data?.type !==
      'FeatureCollection' ||
    !Array.isArray(data.features)
  ) {
    return data
  }

  return {
    ...data,

    features: data.features.map(
      (feature) => ({
        ...feature,

        properties:
          transformProperties(
            feature.properties
          ),
      })
    ),
  }
}

function createNullHeavyData(
  label,
  data
) {
  switch (label) {
    case 'Analysis grid':
      return transformFeatureCollection(
        data,
        nullGridProperties
      )

    case 'Bus stops':
      return transformFeatureCollection(
        data,
        nullBusStopProperties
      )

    case 'Bus routes':
      return transformFeatureCollection(
        data,
        nullBusRouteProperties
      )

    case 'Metro stations':
      return transformFeatureCollection(
        data,
        nullMetroProperties
      )

    case 'Cycleways':
      return transformFeatureCollection(
        data,
        nullCyclewayProperties
      )

    case 'Bus recommendations':
      return transformFeatureCollection(
        data,
        nullBusRecommendationProperties
      )

    case 'Bike recommendations':
      return transformFeatureCollection(
        data,
        nullBikeRecommendationProperties
      )

    case 'Summary':
      return {
        ...data,
        population_estimate: null,
      }

    default:
      return data
  }
}

function getQaScenario() {
  /*
    QA modes only exist while running the Vite
    development server.

    Production builds always return normal data.
  */

  if (!import.meta.env.DEV) {
    return null
  }

  const parameters =
    new URLSearchParams(
      window.location.search
    )

  const scenario =
    parameters.get('qa')

  if (
    scenario === 'empty' ||
    scenario === 'nulls'
  ) {
    return scenario
  }

  return null
}

export function applyQaScenario(
  label,
  data
) {
  const scenario =
    getQaScenario()

  if (!scenario) {
    return data
  }

  if (scenario === 'empty') {
    return createEmptyData(
      label,
      data
    )
  }

  if (scenario === 'nulls') {
    return createNullHeavyData(
      label,
      data
    )
  }

  return data
}