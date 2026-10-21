const REQUIRED_NUMBERS = [
  'population_improved', 'coverage_before_pct', 'coverage_after_pct',
  'coverage_change_pp', 'avg_access_improvement_m', 'affected_cells',
]
const OPTIONAL_NUMBERS = [
  'newly_covered_population', 'newly_covered_cells',
  'unknown_population_cells_affected', 'unknown_population_cells_newly_covered',
]
const TOLERANCE = 1e-8

function object(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} must be a JSON object`)
  }
}
function string(value, label) {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label} must be a nonempty string`)
}
function number(value, label, { signed = false, integer = false, max = Infinity } = {}) {
  if (value === null) return
  if (!Number.isFinite(value) || (!signed && value < 0) || Math.abs(value) > max || (integer && !Number.isInteger(value))) {
    throw new Error(`${label} must be a finite ${signed ? '' : 'nonnegative '}${integer ? 'integer' : 'number'} or null`)
  }
}
function close(a, b) { return Math.abs(a - b) <= TOLERANCE }

export function validateInterventionScenarios(data) {
  object(data, 'Intervention scenarios')
  object(data.metadata, 'Intervention scenarios.metadata')
  object(data.summary, 'Intervention scenarios.summary')
  if (!Array.isArray(data.scenarios)) throw new Error('Intervention scenarios.scenarios must be an array')
  const ids = new Set()
  data.scenarios.forEach((scenario, index) => {
    const label = `Scenario ${index + 1}`
    object(scenario, label)
    string(scenario.intervention_id, `${label}.intervention_id`)
    if (ids.has(scenario.intervention_id)) throw new Error(`Duplicate scenario ID: ${scenario.intervention_id}`)
    ids.add(scenario.intervention_id)
    if (!['bus_stop', 'bike_corridor'].includes(scenario.intervention_type)) {
      throw new Error(`${label}.intervention_type must be bus_stop or bike_corridor`)
    }
    for (const key of REQUIRED_NUMBERS) {
      if (!Object.hasOwn(scenario, key)) throw new Error(`${label} is missing required field ${key}`)
      number(scenario[key], `${label}.${key}`, {
        signed: key === 'coverage_change_pp', integer: key === 'affected_cells',
        max: key.startsWith('coverage_') ? 100 : Infinity,
      })
    }
    for (const key of OPTIONAL_NUMBERS) {
      if (Object.hasOwn(scenario, key)) number(scenario[key], `${label}.${key}`, { integer: key.endsWith('cells') || key.includes('cells_') })
    }
    const { coverage_before_pct: before, coverage_after_pct: after, coverage_change_pp: change } = scenario
    if (before !== null && after !== null) {
      if (after < before - TOLERANCE) throw new Error(`${label} coverage cannot decrease in this model`)
      if (change !== null && !close(after - before, change)) {
        throw new Error(`${label}.coverage_change_pp must equal after minus before in percentage points`)
      }
    }
    if (Object.hasOwn(scenario, 'model_version')) string(scenario.model_version, `${label}.model_version`)
    if (Object.hasOwn(scenario, 'coverage_radius_m') && scenario.coverage_radius_m !== 500) {
      throw new Error(`${label}.coverage_radius_m must be 500 for this comparison`)
    }
    if (scenario.reconciliation !== undefined) {
      const record = scenario.reconciliation
      object(record, `${label}.reconciliation`)
      if (!['match', 'unavailable', 'consistent_with_osm_exclusion'].includes(record.status)) {
        throw new Error(`${label} has an unsupported reconciliation status`)
      }
      for (const key of ['recommendation_value', 'simulation_value', 'difference_population']) {
        if (Object.hasOwn(record, key)) number(record[key], `${label}.reconciliation.${key}`, { signed: key === 'difference_population' })
      }
      if (Object.hasOwn(record, 'explanation')) string(record.explanation, `${label}.reconciliation.explanation`)
      if (record.status === 'consistent_with_osm_exclusion' && scenario.intervention_type !== 'bike_corridor') {
        throw new Error(`${label} OSM cycling exclusions require a bicycle scenario`)
      }
      if (Object.hasOwn(record, 'osm_gate_recomputed_by_simulator') && typeof record.osm_gate_recomputed_by_simulator !== 'boolean') {
        throw new Error(`${label}.reconciliation.osm_gate_recomputed_by_simulator must be boolean`)
      }
      const { recommendation_value: recommendation, simulation_value: simulation, difference_population: difference } = record
      if (record.status === 'match' && Number.isFinite(difference) && !close(difference, 0)) {
        throw new Error(`${label} a matching reconciliation cannot have a population difference`)
      }
      if (record.status === 'consistent_with_osm_exclusion' && Number.isFinite(difference) && difference < -TOLERANCE) {
        throw new Error(`${label} OSM exclusions cannot produce a smaller simulation estimate`)
      }
      if ([recommendation, simulation, difference].every(Number.isFinite) && !close(simulation - recommendation, difference)) {
        throw new Error(`${label} reconciliation population difference is inconsistent`)
      }
      if (Number.isFinite(simulation) && Number.isFinite(scenario.newly_covered_population) && !close(simulation, scenario.newly_covered_population)) {
        throw new Error(`${label} reconciliation must describe newly covered population`)
      }
    }
  })
  if (Object.hasOwn(data.metadata, 'coverage_radius_m') && data.metadata.coverage_radius_m !== 500) {
    throw new Error('Scenario metadata coverage_radius_m must be 500')
  }
  return data
}
