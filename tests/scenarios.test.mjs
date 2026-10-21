import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { validateInterventionScenarios } from '../src/data/validateData.js'
import { createScenarioIndex, findScenario } from '../src/data/scenarios.js'
import { showValue, showPercentage, showPercentagePoints } from '../src/utils/presentation.js'

const read = async name => JSON.parse(await readFile(new URL(`../public/data/${name}`, import.meta.url), 'utf8'))
const document = await read('intervention_scenarios.json')
const bus = await read('bus_recommendations.geojson')
const bike = await read('bike_recommendations.geojson')
const fixture = () => ({ metadata: {}, summary: {}, scenarios: [{
  intervention_id: 'full:original:ID', intervention_type: 'bus_stop',
  population_improved: 100, newly_covered_population: 60,
  coverage_before_pct: 20, coverage_after_pct: 80, coverage_change_pp: 60,
  avg_access_improvement_m: 662.198, affected_cells: 2,
}] })

test('actual document validates without mutation and retains all 34 exact-ID matches', () => {
  const before = JSON.stringify(document)
  assert.equal(validateInterventionScenarios(document), document)
  const index = createScenarioIndex(document)
  assert.equal(index.size, 34)
  for (const [type, collection] of [['Bus recommendation', bus], ['Bike recommendation', bike]]) {
    for (const feature of collection.features) {
      assert.equal(findScenario(index, { type, properties: feature.properties })?.intervention_id, feature.properties.id)
    }
  }
  assert.equal(JSON.stringify(document), before)
})

test('full IDs and intervention types must match; absent scenarios never become zero estimates', () => {
  const index = createScenarioIndex(validateInterventionScenarios(fixture()))
  assert.equal(findScenario(index, { type: 'Bus recommendation', properties: { id: 'full:original:ID' } }), index.get('full:original:ID'))
  for (const selection of [null, { type: 'Bus recommendation', properties: { id: 'ID' } },
    { type: 'Bus recommendation', properties: { id: 'FULL:ORIGINAL:ID' } },
    { type: 'Bike recommendation', properties: { id: 'full:original:ID' } },
    { type: 'Bus stop', properties: { id: 'full:original:ID' } }]) {
    assert.equal(findScenario(index, selection), null)
  }
  assert.equal(createScenarioIndex(null).size, 0)
  assert.equal(validateInterventionScenarios({ metadata: {}, summary: {}, scenarios: [] }).scenarios.length, 0)
})

test('invalid roots, missing required fields, duplicate IDs and unsupported types are rejected', () => {
  for (const invalid of [null, [], {}, { metadata: {}, summary: {}, scenarios: {} }]) assert.throws(() => validateInterventionScenarios(invalid))
  for (const key of ['intervention_id', 'intervention_type', 'population_improved', 'coverage_before_pct',
    'coverage_after_pct', 'coverage_change_pp', 'avg_access_improvement_m', 'affected_cells']) {
    const data = fixture(); delete data.scenarios[0][key]
    assert.throws(() => validateInterventionScenarios(data), key)
  }
  const duplicate = fixture(); duplicate.scenarios.push(structuredClone(duplicate.scenarios[0]))
  assert.throws(() => validateInterventionScenarios(duplicate), /Duplicate/)
  const badType = fixture(); badType.scenarios[0].intervention_type = 'bus_route'
  assert.throws(() => validateInterventionScenarios(badType), /intervention_type/)
})

test('finite numbers, ranges, integer counts and 500m coverage are validated', () => {
  for (const [field, value] of [['population_improved', Infinity], ['newly_covered_population', NaN],
    ['coverage_before_pct', -1], ['coverage_after_pct', 101], ['affected_cells', 1.5],
    ['avg_access_improvement_m', '20'], ['unknown_population_cells_affected', -1], ['coverage_radius_m', 400]]) {
    const data = fixture(); data.scenarios[0][field] = value
    assert.throws(() => validateInterventionScenarios(data), field)
  }
})

test('coverage change uses percentage points, not relative percent or rounded display values', () => {
  assert.equal(validateInterventionScenarios(fixture()).scenarios[0].coverage_change_pp, 60)
  const relative = fixture(); relative.scenarios[0].coverage_change_pp = 300
  assert.throws(() => validateInterventionScenarios(relative))
  const wrong = fixture(); wrong.scenarios[0].coverage_change_pp = 20
  assert.throws(() => validateInterventionScenarios(wrong), /after minus before/)
  const smaller = fixture(); smaller.scenarios[0].coverage_after_pct = 10; smaller.scenarios[0].coverage_change_pp = -10
  assert.throws(() => validateInterventionScenarios(smaller), /cannot decrease/)
  const actual = document.scenarios[0]
  assert.equal(showPercentage(actual.coverage_before_pct), '14.49%')
  assert.equal(showPercentage(actual.coverage_after_pct), '15.67%')
  assert.equal(showPercentagePoints(actual.coverage_change_pp), '+1.18 pp')
})

test('human formatting preserves null/zero distinctions and sensible units', () => {
  assert.equal(showValue(910213.3988891606), '910,213')
  assert.equal(showValue(34203.403299331665), '34,203')
  assert.equal(showValue(662.198, ' m'), '662 m')
  assert.equal(showValue(1553.6149, ' m'), '1.55 km')
  assert.equal(showPercentage(0), '0.0%')
  assert.equal(showPercentagePoints(0), '0.0 pp')
  assert.equal(showPercentagePoints(0.001), '+<0.01 pp')
  for (const value of [null, undefined, Infinity, NaN]) {
    assert.equal(showPercentage(value), 'Unavailable')
    assert.equal(showPercentagePoints(value), 'Unavailable')
  }
  const data = fixture()
  for (const key of Object.keys(data.scenarios[0])) if (typeof data.scenarios[0][key] === 'number') data.scenarios[0][key] = null
  assert.equal(validateInterventionScenarios(data).scenarios[0].population_improved, null)
})

test('population improved remains distinct and all five OSM-exclusion records survive', () => {
  const valid = validateInterventionScenarios(document)
  assert.ok(valid.scenarios[0].population_improved > valid.scenarios[0].newly_covered_population)
  const differences = valid.scenarios.filter(s => s.reconciliation?.status === 'consistent_with_osm_exclusion')
  assert.equal(differences.length, 5)
  for (const scenario of differences) {
    assert.equal(scenario.intervention_type, 'bike_corridor')
    assert.equal(scenario.reconciliation.osm_gate_recomputed_by_simulator, false)
    assert.equal(scenario.reconciliation.simulation_value, scenario.newly_covered_population)
    assert.ok(scenario.reconciliation.recommendation_value < scenario.newly_covered_population)
    assert.match(scenario.reconciliation.explanation, /cannot independently verify/)
  }
  const inconsistent = structuredClone(document)
  inconsistent.scenarios[0].reconciliation.simulation_value += 100
  assert.throws(() => validateInterventionScenarios(inconsistent), /inconsistent|newly covered/)
})
