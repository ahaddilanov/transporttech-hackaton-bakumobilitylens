// Requires the authorized complete real snapshot; run npm run test:real-data.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { validateInterventionScenarios } from '../src/data/validateData.js'
import { createScenarioIndex, findScenario } from '../src/data/scenarios.js'

const read = async name => JSON.parse(await readFile(new URL(`../public/data/${name}`, import.meta.url), 'utf8'))
const document = await read('intervention_scenarios.json')
const bus = await read('bus_recommendations.geojson')
const bike = await read('bike_recommendations.geojson')

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
