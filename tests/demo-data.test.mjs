import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import { createDemoData } from '../scripts/create_demo_data.mjs'
import * as validators from '../src/data/validateData.js'
import { createScenarioIndex, findScenario } from '../src/data/scenarios.js'
import viteConfig from '../vite.config.js'

const data = createDemoData()
const validatorsByFile = {
  'grid.geojson': 'validateGrid', 'bus_stops.geojson': 'validateBusStops',
  'bus_routes.geojson': 'validateBusRoutes', 'metro_stations.geojson': 'validateMetroStations',
  'cycleways.geojson': 'validateCycleways', 'bus_recommendations.geojson': 'validateBusRecommendations',
  'bike_recommendations.geojson': 'validateBikeRecommendations', 'summary.json': 'validateSummary',
  'intervention_scenarios.json': 'validateInterventionScenarios',
}

test('all synthetic assets are reproducible, explicitly labeled and V1 compatible', async () => {
  assert.deepEqual(createDemoData(), data)
  const directory = new URL('../demo/public/data/', import.meta.url)
  assert.deepEqual((await readdir(directory)).sort(), Object.keys(data).sort())
  const ids = new Set()
  for (const [name, document] of Object.entries(data)) {
    assert.equal(await readFile(new URL(name, directory), 'utf8'), `${JSON.stringify(document, null, 2)}\n`)
    assert.equal(validators[validatorsByFile[name]](document), document)
    assert.equal(document.metadata?.synthetic ?? document.synthetic, true)
    for (const feature of document.features ?? []) {
      assert.match(feature.id, /^synthetic:/)
      assert.equal(feature.id, feature.properties.id)
      assert.equal(ids.has(feature.id), false)
      ids.add(feature.id)
      assert.equal(feature.properties.source, 'Synthetic example')
    }
  }
})

test('synthetic summaries, exact scenario matches, percentage points and nulls agree', () => {
  const cells = data['grid.geojson'].features
  const summary = data['summary.json']
  assert.equal(summary.grid_cells, cells.length)
  assert.equal(summary.population_estimate, cells.reduce((sum, f) => sum + (f.properties.population ?? 0), 0))
  for (const [field, score] of [['high_bus_priority_cells', 'bus_priority'], ['high_bike_priority_cells', 'bike_priority']]) {
    assert.equal(summary[field], cells.filter(f => f.properties[score] !== null && f.properties[score] >= 60).length)
  }
  assert.ok(cells.some(f => f.properties.population === null))
  assert.ok(cells.some(f => f.properties.population === 0))
  const index = createScenarioIndex(data['intervention_scenarios.json'])
  assert.equal(index.size, 2)
  for (const [name, type, field] of [['bus', 'Bus recommendation', 'population_affected'], ['bike', 'Bike recommendation', 'population_coverage_gain']]) {
    const feature = data[`${name}_recommendations.geojson`].features[0]
    const scenario = findScenario(index, { type, properties: feature.properties })
    assert.equal(scenario.newly_covered_population, feature.properties[field])
    assert.ok(scenario.population_improved > scenario.newly_covered_population)
    assert.equal(scenario.coverage_change_pp, scenario.coverage_after_pct - scenario.coverage_before_pct)
    assert.ok(Math.abs(scenario.coverage_change_pp - 100 * scenario.newly_covered_population / summary.population_estimate) < 1e-8)
  }
})

test('demo builds isolate their public directory and output from real static exports', () => {
  const demo = viteConfig({ mode: 'demo' })
  const normal = viteConfig({ mode: 'production' })
  assert.equal(demo.publicDir, 'demo/public')
  assert.equal(demo.build.outDir, 'dist-demo')
  assert.equal(normal.publicDir, 'public')
  assert.equal(normal.build.outDir, 'dist')
})
