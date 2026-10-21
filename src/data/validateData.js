function requireFeatureCollection(data, label) {
  if (!data || data.type !== 'FeatureCollection' || !Array.isArray(data.features)) {
    throw new Error(`${label} must be a GeoJSON FeatureCollection`)
  }
}

function requireGeometry(feature, allowedTypes, label) {
  const geometryType = feature?.geometry?.type

  if (!allowedTypes.includes(geometryType)) {
    throw new Error(
      `${label} has invalid geometry "${geometryType ?? 'missing'}". Expected ${allowedTypes.join(' or ')}`
    )
  }
}

function requireProperty(properties, key, label) {
  if (!Object.prototype.hasOwnProperty.call(properties, key)) {
    throw new Error(`${label} is missing required property "${key}"`)
  }
}

function requireString(value, key, label, allowNull = false) {
  if (allowNull && value === null) {
    return
  }

  if (typeof value !== 'string') {
    throw new Error(`${label}.${key} must be a string`)
  }
}

function requireNumber(value, key, label, allowNull = false) {
  if (allowNull && value === null) {
    return
  }

  if (typeof value !== 'number' || Number.isNaN(value)) {
    throw new Error(`${label}.${key} must be a number`)
  }
}

function requireInteger(value, key, label, allowNull = false) {
  if (allowNull && value === null) {
    return
  }

  if (!Number.isInteger(value)) {
    throw new Error(`${label}.${key} must be an integer`)
  }
}

function requireScore(value, key, label, allowNull = true) {
  if (allowNull && value === null) {
    return
  }

  requireNumber(value, key, label)

  if (value < 0 || value > 100) {
    throw new Error(`${label}.${key} must be between 0 and 100`)
  }
}

function requireStringArray(value, key, label) {
  if (!Array.isArray(value) || !value.every((item) => typeof item === 'string')) {
    throw new Error(`${label}.${key} must be an array of strings`)
  }
}

function validateFeatures(data, config) {
  requireFeatureCollection(data, config.label)

  data.features.forEach((feature, index) => {
    const label = `${config.label} feature ${index + 1}`

    requireGeometry(feature, config.geometryTypes, label)

    if (!feature.properties || typeof feature.properties !== 'object') {
      throw new Error(`${label} must contain a properties object`)
    }

    config.validate(feature.properties, label)
  })

  return data
}

export function validateBusStops(data) {
  return validateFeatures(data, {
    label: 'Bus stops',
    geometryTypes: ['Point'],
    validate(properties, label) {
      requireProperty(properties, 'id', label)
      requireProperty(properties, 'name', label)

      requireString(properties.id, 'id', label)
      requireString(properties.name, 'name', label, true)
    },
  })
}

export function validateBusRoutes(data) {
  return validateFeatures(data, {
    label: 'Bus routes',
    geometryTypes: ['LineString', 'MultiLineString'],
    validate(properties, label) {
      const required = [
        'id',
        'name',
        'route_ref',
        'avg_daily_validations',
      ]

      required.forEach((key) => requireProperty(properties, key, label))

      requireString(properties.id, 'id', label)
      requireString(properties.name, 'name', label, true)
      requireString(properties.route_ref, 'route_ref', label, true)
      requireNumber(
        properties.avg_daily_validations,
        'avg_daily_validations',
        label,
        true
      )
    },
  })
}

export function validateMetroStations(data) {
  return validateFeatures(data, {
    label: 'Metro stations',
    geometryTypes: ['Point'],
    validate(properties, label) {
      const required = ['id', 'name', 'avg_daily_entries']

      required.forEach((key) => requireProperty(properties, key, label))

      requireString(properties.id, 'id', label)
      requireString(properties.name, 'name', label, true)
      requireNumber(
        properties.avg_daily_entries,
        'avg_daily_entries',
        label,
        true
      )
    },
  })
}

export function validateCycleways(data) {
  return validateFeatures(data, {
    label: 'Cycleways',
    geometryTypes: ['LineString', 'MultiLineString'],
    validate(properties, label) {
      const required = ['id', 'name', 'length_m']

      required.forEach((key) => requireProperty(properties, key, label))

      requireString(properties.id, 'id', label)
      requireString(properties.name, 'name', label, true)
      requireNumber(properties.length_m, 'length_m', label, true)
    },
  })
}

export function validateGrid(data) {
  return validateFeatures(data, {
    label: 'Analysis grid',
    geometryTypes: ['Polygon', 'MultiPolygon'],
    validate(properties, label) {
      const required = [
        'id',
        'population',
        'nearest_bus_stop_m',
        'nearest_metro_m',
        'nearest_cycleway_m',
        'bus_stops_500m',
        'bus_routes_nearby',
        'pois_nearby',
        'bus_priority',
        'bike_priority',
        'mobility_gap',
      ]

      required.forEach((key) => requireProperty(properties, key, label))

      requireString(properties.id, 'id', label)

      requireNumber(properties.population, 'population', label, true)
      requireNumber(
        properties.nearest_bus_stop_m,
        'nearest_bus_stop_m',
        label,
        true
      )
      requireNumber(
        properties.nearest_metro_m,
        'nearest_metro_m',
        label,
        true
      )
      requireNumber(
        properties.nearest_cycleway_m,
        'nearest_cycleway_m',
        label,
        true
      )

      requireInteger(properties.bus_stops_500m, 'bus_stops_500m', label, true)
      requireInteger(
        properties.bus_routes_nearby,
        'bus_routes_nearby',
        label,
        true
      )
      requireInteger(properties.pois_nearby, 'pois_nearby', label, true)

      requireScore(properties.bus_priority, 'bus_priority', label)
      requireScore(properties.bike_priority, 'bike_priority', label)
      requireScore(properties.mobility_gap, 'mobility_gap', label)
    },
  })
}

export function validateBusRecommendations(data) {
  return validateFeatures(data, {
    label: 'Bus recommendations',
    geometryTypes: ['Point'],
    validate(properties, label) {
      const required = [
        'id',
        'priority',
        'population_affected',
        'current_access_m',
        'new_access_m',
        'access_improvement_m',
        'reason',
      ]

      required.forEach((key) => requireProperty(properties, key, label))

      requireString(properties.id, 'id', label)
      requireScore(properties.priority, 'priority', label, false)

      requireNumber(
        properties.population_affected,
        'population_affected',
        label,
        true
      )
      requireNumber(
        properties.current_access_m,
        'current_access_m',
        label,
        true
      )
      requireNumber(properties.new_access_m, 'new_access_m', label, true)
      requireNumber(
        properties.access_improvement_m,
        'access_improvement_m',
        label,
        true
      )

      requireStringArray(properties.reason, 'reason', label)
    },
  })
}

export function validateBikeRecommendations(data) {
  return validateFeatures(data, {
    label: 'Bike recommendations',
    geometryTypes: ['LineString', 'MultiLineString'],
    validate(properties, label) {
      const required = [
        'id',
        'priority',
        'length_m',
        'population_coverage_gain',
        'start_name',
        'end_name',
        'reason',
      ]

      required.forEach((key) => requireProperty(properties, key, label))

      requireString(properties.id, 'id', label)
      requireScore(properties.priority, 'priority', label, false)

      requireNumber(properties.length_m, 'length_m', label, true)
      requireNumber(
        properties.population_coverage_gain,
        'population_coverage_gain',
        label,
        true
      )

      requireString(properties.start_name, 'start_name', label, true)
      requireString(properties.end_name, 'end_name', label, true)

      requireStringArray(properties.reason, 'reason', label)
    },
  })
}

export function validateSummary(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('Summary must be a JSON object')
  }

  const required = [
    'generated_at',
    'grid_cells',
    'population_estimate',
    'high_bus_priority_cells',
    'high_bike_priority_cells',
  ]

  required.forEach((key) => requireProperty(data, key, 'Summary'))

  requireString(data.generated_at, 'generated_at', 'Summary')
  requireInteger(data.grid_cells, 'grid_cells', 'Summary')
  requireNumber(
    data.population_estimate,
    'population_estimate',
    'Summary',
    true
  )
  requireInteger(
    data.high_bus_priority_cells,
    'high_bus_priority_cells',
    'Summary'
  )
  requireInteger(
    data.high_bike_priority_cells,
    'high_bike_priority_cells',
    'Summary'
  )

  if (Number.isNaN(Date.parse(data.generated_at))) {
    throw new Error('Summary.generated_at must be a valid ISO-8601 timestamp')
  }

  return data
}
// Keep scenario validation alongside the existing loading validators, without
// changing the GeoJSON/Shared Contract V1 validators above.
export { validateInterventionScenarios } from './validateScenarios.js'
