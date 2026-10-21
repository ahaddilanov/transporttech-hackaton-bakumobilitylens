import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { showValue, showPercentage, showPercentagePoints } from '../src/utils/presentation.js'
import { socket, exceptions, call, evaluate, sleep, settle, load, click, focus, key, viewport } from './browser-client.mjs'

const read = async name => JSON.parse(await readFile(new URL(`../public/data/${name}`, import.meta.url), 'utf8'))
const saved = await read('intervention_scenarios.json')
const bike = await read('bike_recommendations.geojson')
const index = new Map(saved.scenarios.map(s => [s.intervention_id, s]))
let mode = 'hold'
const held = []
const pendingResponses = []
let requestCount = 0
let interceptionError
function payload() {
  const data = structuredClone(saved)
  if (mode === 'empty') data.scenarios = []
  if (mode === 'duplicate') data.scenarios.push(structuredClone(data.scenarios[0]))
  if (mode === 'null' || mode === 'zero') {
    for (const s of data.scenarios) {
      for (const field of ['population_improved', 'newly_covered_population', 'coverage_before_pct', 'coverage_after_pct', 'coverage_change_pp', 'affected_cells']) s[field] = mode === 'null' ? null : 0
      s.avg_access_improvement_m = null
      delete s.reconciliation
    }
  }
  return data
}
async function respond(requestId) {
  await call('Fetch.fulfillRequest', {
    requestId, responseCode: mode === 'missing' ? 404 : 200,
    responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
    body: Buffer.from(JSON.stringify(payload())).toString('base64'),
  })
}
socket.addEventListener('message', event => {
  const message = JSON.parse(event.data)
  if (message.method !== 'Fetch.requestPaused') return
  requestCount++
  if (mode === 'hold') held.push(message.params.requestId)
  else pendingResponses.push(respond(message.params.requestId).catch(error => { interceptionError = error }))
})
async function waitFor(expression, label) {
  for (let n = 0; n < 150; n++) {
    await sleep(100)
    if (await evaluate(expression)) return
  }
  assert.fail(label)
}
async function expandBus() {
  await click('.ranking-collapsed'); await click('.ranking-card'); await sleep(800)
  await click('.simulation-comparison > summary')
}
async function checkValues(scenario) {
  const expected = {
    coverage_before_pct: showPercentage(scenario.coverage_before_pct),
    coverage_after_pct: showPercentage(scenario.coverage_after_pct),
    coverage_change_pp: showPercentagePoints(scenario.coverage_change_pp),
    newly_covered_population: showValue(scenario.newly_covered_population),
    population_improved: showValue(scenario.population_improved),
    avg_access_improvement_m: showValue(scenario.avg_access_improvement_m, ' m'),
  }
  for (const [field, value] of Object.entries(expected)) {
    assert.equal(await evaluate(`document.querySelector('[data-scenario-field="${field}"]').textContent`), value, field)
  }
}
async function snapshot(name) {
  if (!process.env.SCREENSHOT_DIR) return
  await mkdir(process.env.SCREENSHOT_DIR, { recursive: true })
  const { data } = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(`${process.env.SCREENSHOT_DIR}/${name}.png`, Buffer.from(data, 'base64'))
}
try {
  await call('Page.enable'); await call('Runtime.enable'); await call('Network.enable')
  await call('Network.setBlockedURLs', { urls: ['*tile.openstreetmap.org*'] })
  await call('Fetch.enable', { patterns: [{ urlPattern: '*intervention_scenarios.json*' }] })
  await viewport(1440, 1000)
  await call('Page.navigate', { url: process.env.APP_URL ?? 'http://127.0.0.1:5173/' })
  await waitFor(`!!document.querySelector('canvas') && !!document.querySelector('.ranking-collapsed')`, 'Grid must load while scenarios wait')
  await expandBus()
  assert.match(await evaluate(`document.querySelector('.simulation-comparison').textContent`), /Loading saved/)
  // Observe geometry creation/style calls while only scenario data changes.
  await evaluate(`(async () => {
    const url=performance.getEntriesByType('resource').find(e=>e.name.includes('/deps/leaflet.js')).name;
    const L=(await import(url)).default;
    window.guard={L,gridStyles:0,adds:0,layers:new Set(),canvas:document.querySelector('canvas')};
    guard.style=L.Path.prototype.setStyle;guard.add=L.GeoJSON.prototype.addData;
    L.Path.prototype.setStyle=function(style){if(this.feature?.properties?.mobility_gap!==undefined){guard.gridStyles++;guard.layers.add(this)}return guard.style.call(this,style)};
    L.GeoJSON.prototype.addData=function(data){guard.adds++;return guard.add.call(this,data)};
  })()`)
  await click('.analysis-tabs button:nth-child(2)')
  assert.equal(await evaluate('guard.layers.size'), 35029)
  await evaluate('guard.gridStyles=0;guard.adds=0')
  mode = 'real'
  assert.ok(held.length > 0)
  await Promise.all(held.map(respond))
  await waitFor(`!!document.querySelector('[data-scenario-field="coverage_before_pct"]') && !document.querySelector('.data-status-stack')`, 'Scenario must load')
  let id = await evaluate(`document.querySelector('.feature-identifier code').textContent`)
  await checkValues(index.get(id))
  assert.equal(await evaluate('guard.gridStyles'), 0, 'Loading scenarios must not restyle grid cells')
  assert.equal(await evaluate('guard.adds'), 0, 'Loading scenarios must not create GeoJSON layers')
  assert.equal(await evaluate('guard.canvas===document.querySelector("canvas") && [...guard.layers].every(layer=>!!layer._map)'), true)
  const requestsAfterLoad = requestCount
  for (let n = 0; n < 4; n++) await click('.simulation-comparison > summary')
  assert.equal(await evaluate('guard.gridStyles'), 0)
  assert.equal(await evaluate('guard.adds'), 0)
  assert.equal(requestCount, requestsAfterLoad, 'Expanding details must not reload scenario data')
  await evaluate('guard.L.Path.prototype.setStyle=guard.style;guard.L.GeoJSON.prototype.addData=guard.add;void 0')
  assert.match(await evaluate(`document.querySelector('.simulation-comparison').textContent`), /already covered or still farther/)
  await snapshot('bus-before-after')
  await click('.ranking-tabs button:nth-child(2)')
  await click('.ranking-footer button')
  const sorted = [...bike.features].sort((a, b) => b.properties.priority - a.properties.priority)
  const rank = sorted.findIndex(f => index.get(f.properties.id)?.reconciliation.status === 'consistent_with_osm_exclusion')
  await click('.ranking-card', rank); await sleep(800)
  id = await evaluate(`document.querySelector('.feature-identifier code').textContent`)
  assert.equal(id, sorted[rank].properties.id)
  assert.equal(await evaluate(`document.querySelector('.simulation-comparison').open`), false, 'New selection starts collapsed')
  await focus('.simulation-comparison > summary'); await key('Enter')
  await checkValues(index.get(id))
  assert.match(await evaluate(`document.querySelector('.simulation-baseline').textContent`), /AYNA bicycle lanes only/)
  assert.equal(await evaluate(`document.querySelector('.simulation-reconciliation').dataset.reconciliationStatus`), 'consistent_with_osm_exclusion')
  assert.match(await evaluate(`document.querySelector('.simulation-reconciliation').textContent`), /did not independently recheck/)
  assert.equal(await evaluate(`document.querySelector('[data-scenario-field="recommendation_value"]').textContent`), showValue(index.get(id).reconciliation.recommendation_value))
  await click('.simulation-method-note > summary')
  assert.match(await evaluate(`document.querySelector('.simulation-method-note').textContent`), /cannot independently verify/)
  await click('.theme-toggle')
  await snapshot('bike-osm-difference-dark')
  await viewport(390, 844); await sleep(300)
  await evaluate(`document.querySelector('.simulation-comparison').scrollIntoView();void 0`)
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true)
  await snapshot('comparison-mobile')
  await viewport(1440, 1000)
  for (const fixtureMode of ['empty', 'null', 'zero', 'missing', 'duplicate']) {
    mode = fixtureMode
    await call('Page.navigate', { url: process.env.APP_URL ?? 'http://127.0.0.1:5173/' })
    await waitFor(`!!document.querySelector('.ranking-collapsed') && !document.querySelector('.data-status-loading')`, `Load ${mode}`)
    await expandBus()
    if (mode === 'empty') {
      assert.match(await evaluate(`document.querySelector('.simulation-comparison').textContent`), /No saved simulation matches/)
    } else if (mode === 'missing' || mode === 'duplicate') {
      assert.match(await evaluate(`document.querySelector('.simulation-comparison').textContent`), /Saved simulation data is unavailable/)
      assert.ok(await evaluate(`!!document.querySelector('canvas') && !!document.querySelector('.feature-panel h2')`))
    } else if (mode === 'null') {
      assert.equal(await evaluate(`[...document.querySelectorAll('.simulation-metrics dd')].every(e=>e.textContent==='Unavailable')`), true)
    } else {
      assert.equal(await evaluate(`document.querySelector('[data-scenario-field="population_improved"]').textContent`), '0')
      assert.equal(await evaluate(`document.querySelector('[data-scenario-field="coverage_change_pp"]').textContent`), '0.0 pp')
      assert.equal(await evaluate(`document.querySelector('[data-scenario-field="avg_access_improvement_m"]').textContent`), 'Unavailable')
    }
  }
  await Promise.all(pendingResponses)
  assert.equal(interceptionError, undefined)
  assert.equal(exceptions.length, 0, JSON.stringify(exceptions))
  console.log(JSON.stringify({ passed: true, checked: 'loading; complete-ID bus and bike matches; six displayed metrics; OSM policy/status/limitations; native collapse + keyboard; unchanged grid on load/toggle; theme/mobile; empty/null/zero/404/duplicate data' }, null, 2))
} finally {
  await call('Fetch.disable')
  socket.close()
}
