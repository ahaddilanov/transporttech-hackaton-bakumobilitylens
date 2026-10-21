// Start an isolated Chrome tab at about:blank and the clone's dev:demo server.
// APP_URL=http://127.0.0.1:5174/ node tests/demo-browser-check.mjs
import assert from 'node:assert/strict'
import { socket, exceptions, call, evaluate, sleep, load, click, focus, key, viewport } from './browser-client.mjs'

try {
  await call('Page.enable'); await call('Runtime.enable'); await call('Network.enable')
  await call('Network.setBlockedURLs', { urls: ['*tile.openstreetmap.org*'] })
  await viewport(1440, 1000)
  await load()
  assert.equal(await evaluate('document.title'), 'Baku Mobility Lens')
  assert.ok(await evaluate(`!!document.querySelector('.leaflet-control-attribution a[href="https://www.openstreetmap.org/copyright"]')`))
  assert.match(await evaluate(`document.querySelector('.brand-copy').textContent`), /Synthetic examples/)
  assert.equal(await evaluate(`document.querySelector('.data-mode-badge').textContent.trim()`), 'Synthetic demo')
  const counts = await evaluate(`(async () => {
    const files=['grid','bus_stops','bus_routes','metro_stations','cycleways','bus_recommendations','bike_recommendations'];
    const counts={};for(const file of files){const data=await (await fetch('/data/'+file+'.geojson')).json();
      if(data.metadata.synthetic!==true)throw new Error('Unexpected real data');counts[file]=data.features.length;}
    return counts;
  })()`)
  assert.deepEqual(counts, { grid: 4, bus_stops: 2, bus_routes: 1, metro_stations: 1,
    cycleways: 1, bus_recommendations: 1, bike_recommendations: 1 })
  await click('.ranking-collapsed')
  await focus('.ranking-card'); await key('Enter'); await sleep(700)
  await click('.simulation-comparison > summary')
  assert.equal(await evaluate(`document.querySelector('[data-scenario-field="population_improved"]').textContent`), '300')
  assert.equal(await evaluate(`document.querySelector('[data-scenario-field="newly_covered_population"]').textContent`), '100')
  assert.equal(await evaluate(`document.querySelector('[data-scenario-field="coverage_change_pp"]').textContent`), '+33.33 pp')
  await click('.ranking-tabs button:nth-child(2)'); await click('.ranking-card'); await sleep(700)
  await click('.simulation-comparison > summary')
  assert.equal(await evaluate(`document.querySelector('[data-scenario-field="newly_covered_population"]').textContent`), '200')
  assert.equal(await evaluate(`document.querySelectorAll('.leaflet-tooltip').length`), 0)
  await viewport(390, 844)
  assert.match(await evaluate(`document.querySelector('.brand-copy').innerText`), /Synthetic examples/)
  assert.equal(await evaluate('document.documentElement.scrollWidth > innerWidth'), false)
  assert.equal(exceptions.length, 0, JSON.stringify(exceptions))
  console.log(JSON.stringify({ passed: true, counts, checked: 'clone-safe synthetic assets, visible labeling, keyboard/ranking selection, saved bus/bike comparisons, no hover labels, mobile layout' }, null, 2))
} finally {
  socket.close()
}
