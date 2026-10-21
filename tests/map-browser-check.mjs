// Real-data browser regression checks; setup is in FRONTEND_PERFORMANCE.md.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { socket, exceptions, call, evaluate, sleep, settle, load, click, mouse, focus, key, viewport } from './browser-client.mjs'
async function quietMap() {
  assert.equal(await evaluate(`document.querySelectorAll('.leaflet-tooltip').length`), 0, 'No automatic or stale labels')
  assert.equal(await evaluate(`Object.values(check.map._layers).filter(layer=>layer.feature).every(layer=>!layer.getTooltip?.())`), true)
  assert.equal(await evaluate(`check.originalLayers.every(layer=>layer.options.weight===0.8 && layer.options.opacity===0.62 && layer.options.fillOpacity===0.42)`), true, 'Grid styles have no hover changes')
  assert.equal(await evaluate(`Object.values(check.map._layers).filter(layer=>layer.options?.interactive!==false && layer.getElement?.()).every(layer=>{
    const before=check.svgStyles[layer.feature?.properties?.id];
    return !before || JSON.stringify([layer.options.weight,layer.options.radius,layer.options.opacity,layer.options.fillOpacity])===before;
  })`), true, 'Source transport styles have no stale highlights')
}
async function viewportCoverage() {
  assert.equal(await evaluate(`(() => {
    const renderer=check.originalLayers[0]._renderer;
    const visible=new Set(renderer._visibleLayers);
    const bounds=check.map.getBounds();
    return check.originalLayers.every(layer=>!layer.getBounds().intersects(bounds) || visible.has(layer));
  })()`), true, 'Every viewport grid cell remains in the renderer working set')
}
async function snapshot(name) {
  if (!process.env.SCREENSHOT_DIR) return
  await mkdir(process.env.SCREENSHOT_DIR, { recursive: true })
  const { data } = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(`${process.env.SCREENSHOT_DIR}/${name}.png`, Buffer.from(data, 'base64'))
}
async function svgPoint(prefix) {
  return evaluate(`(() => {
    const elements=[...document.querySelectorAll('path.keyboard-map-feature')].filter(e=>e.getAttribute('aria-label').startsWith(${JSON.stringify(prefix)}));
    for(const element of elements){
      const matrix=element.getScreenCTM();
      if(!matrix)continue;
      const bbox=element.getBBox();
      if(bbox.width+bbox.height<0.1)continue;
      const length=element.getTotalLength();
      const points=[{x:bbox.x+bbox.width/2,y:bbox.y+bbox.height/2},...[.1,.25,.4,.5,.6,.75,.9].map(t=>element.getPointAtLength(length*t))];
      for(const point of points){
        const p=new DOMPoint(point.x,point.y).matrixTransform(matrix);
        if(p.x<50||p.y<160||p.x>innerWidth-50||p.y>innerHeight-100)continue;
        if(document.elementFromPoint(p.x,p.y)!==element)continue;
        const layer=Object.values(check.map._layers).find(layer=>layer.getElement?.()===element);
        return {x:p.x,y:p.y,id:layer.feature.properties.id};
      }
    }
    return null;
  })()`)
}
async function clickFeature(prefix) {
  const point = await svgPoint(prefix)
  assert.ok(point, `A visible clickable ${prefix} must be available`)
  await mouse({ x: point.x, y: point.y }, true); await settle()
  assert.equal(await evaluate(`document.querySelector('.feature-identifier code').textContent`), point.id)
  assert.equal(await evaluate(`document.querySelectorAll('.leaflet-selection-pane-pane path').length`), 2)
  await quietMap()
  return point
}
async function drag(from, to) {
  await call('Input.dispatchMouseEvent', { type: 'mouseMoved', ...from })
  await call('Input.dispatchMouseEvent', { type: 'mousePressed', ...from, button: 'left', clickCount: 1 })
  for (let step = 1; step <= 8; step++) {
    await call('Input.dispatchMouseEvent', { type: 'mouseMoved', x: from.x + (to.x-from.x)*step/8, y: from.y + (to.y-from.y)*step/8, buttons: 1 })
    await sleep(20)
  }
  await call('Input.dispatchMouseEvent', { type: 'mouseReleased', ...to, button: 'left', clickCount: 1 })
  let idle = false
  for (let n = 0; n < 100; n++) {
    await sleep(20)
    idle = await evaluate('!check.map._animatingZoom && !check.map._panAnim?._inProgress && !check.map.dragging.moving()')
    if (idle) break
  }
  assert.ok(idle, 'Drag inertia must finish before viewport coverage is checked')
  await settle()
}
try {
  await call('Page.enable')
  await call('Runtime.enable')
  await call('Network.enable')
  await call('Network.setBlockedURLs', { urls: ['*tile.openstreetmap.org*'] })
  await viewport(1440, 1000)
  await load()
  const initial = await evaluate(`({readyMs:performance.now(), paths:document.querySelectorAll('path').length, gridPaths:document.querySelectorAll('.leaflet-analysis-grid-pane-pane path').length, canvas:document.querySelectorAll('canvas').length})`)
  assert.equal(initial.gridPaths, 0)
  assert.equal(initial.canvas, 1)
  // Observe Leaflet method calls in the existing dev module, without changing app data.
  await evaluate(`(async () => {
    const url=performance.getEntriesByType('resource').find(e=>e.name.includes('/deps/leaflet.js')).name;
    const L=(await import(url)).default;
    window.check={L,layers:new Set(),additions:0,canvas:document.querySelector('canvas')};
    check.originalStyle=L.Path.prototype.setStyle;
    check.originalAdd=L.GeoJSON.prototype.addData;
    L.Path.prototype.setStyle=function(style){if(this.feature?.properties?.mobility_gap!==undefined)check.layers.add(this);return check.originalStyle.call(this,style)};
    L.GeoJSON.prototype.addData=function(data){check.additions++;return check.originalAdd.call(this,data)};
  })()`)
  const started = await evaluate('performance.now()')
  await click('.analysis-tabs button:nth-child(2)')
  const metricMs = await evaluate(`performance.now()-${started}`)
  assert.equal(await evaluate('check.layers.size'), 35029)
  await evaluate(`check.originalLayers=[...check.layers];check.layers.clear();
    check.map=check.originalLayers.find(layer=>layer._map)._map;
    check.svgStyles=Object.fromEntries(Object.values(check.map._layers).filter(layer=>layer.options?.interactive!==false && layer.getElement?.()).map(layer=>[layer.feature.properties.id,JSON.stringify([layer.options.weight,layer.options.radius,layer.options.opacity,layer.options.fillOpacity])]));
    check.rings=check.originalLayers.map(layer=>layer.getLatLngs());
    check.originalContains=check.L.Polygon.prototype._containsPoint;
    check.hitTests=0;
    check.L.Polygon.prototype._containsPoint=function(...args){check.hitTests++;return check.originalContains.apply(this,args)};
  `)
  await click('.analysis-tabs button:nth-child(3)')
  assert.equal(await evaluate('check.additions'), 0, 'Metric changes must not recreate GeoJSON')
  assert.equal(await evaluate('check.originalLayers.every(layer=>check.layers.has(layer) && !layer.getTooltip())'), true)
  assert.equal(await evaluate('check.canvas===document.querySelector("canvas")'), true)
  assert.equal(await evaluate(`check.originalLayers.every(layer=>{
    const score=layer.feature.properties.bike_priority;
    const expected=score==null?'#9ca3af':score>=75?'#dc2626':score>=50?'#f97316':score>=25?'#eab308':'#22c55e';
    return layer.options.fillColor===expected;
  })`), true)
  for (const [index, metric] of [[1,'mobility_gap'],[2,'bus_priority'],[3,'bike_priority']]) {
    await click(`.analysis-tabs button:nth-child(${index})`)
    assert.equal(await evaluate(`check.originalLayers.every(layer=>{
      const score=layer.feature.properties[${JSON.stringify(metric)}];
      const expected=score==null?'#9ca3af':score>=75?'#dc2626':score>=50?'#f97316':score>=25?'#eab308':'#22c55e';
      return layer.options.fillColor===expected;
    })`),true)
  }
  assert.equal(await evaluate('check.additions'), 0)
  await evaluate('check.L.Path.prototype.setStyle=check.originalStyle;check.L.GeoJSON.prototype.addData=check.originalAdd')
  await mouse({ x: 1100, y: 350 }); await sleep(150)
  await quietMap()
  assert.equal(await evaluate('check.hitTests'), 0, 'Pointer movement must not hit-test polygons')
  await mouse({ x: 1100, y: 350 }, true); await settle()
  assert.match(await evaluate(`document.querySelector('.feature-panel').innerText`), /Grid cell/)
  assert.equal(await evaluate(`document.querySelectorAll('.leaflet-selection-pane-pane path').length`), 2)
  await mouse({ x: 1000, y: 900 }, true); await settle()
  assert.equal(await evaluate(`!!document.querySelector('.inspector-collapsed')`), true, 'Empty map click clears selection')
  await mouse({ x: 1100, y: 350 }, true); await settle()
  await key('Escape')
  assert.equal(await evaluate(`!!document.querySelector('.inspector-collapsed')`), true)
  await viewportCoverage()
  const centerBefore = await evaluate('check.map.getCenter().toString()')
  await evaluate('check.hitTests=0')
  await drag({ x: 1000, y: 700 }, { x: 1100, y: 700 })
  assert.notEqual(await evaluate('check.map.getCenter().toString()'), centerBefore)
  assert.equal(await evaluate('check.hitTests'), 0, 'Dragging must not hit-test polygons')
  assert.equal(await evaluate(`!!document.querySelector('.inspector-collapsed')`), true)
  await quietMap(); await viewportCoverage()
  const zoomBefore = await evaluate('check.map.getZoom()')
  await click('.leaflet-control-zoom-in'); await sleep(500)
  assert.equal(await evaluate('check.map.getZoom()'), zoomBefore + 1)
  await viewportCoverage()
  await focus('.skip-link'); await key('Enter')
  assert.equal(await evaluate('document.activeElement.id'), 'analysis-controls')
  await click('.grid-browser > button')
  await focus('.grid-browser-results li button'); await key('Enter'); await sleep(850)
  assert.match(await evaluate(`document.querySelector('.feature-panel').innerText`), /Grid cell/)
  assert.equal(await evaluate(`document.querySelectorAll('.grid-browser-results li').length`), 10)
  await click('.grid-browser-pages button:last-child')
  assert.match(await evaluate(`document.querySelector('.grid-browser-pages').textContent`), /11–20/)
  await click('.layers-collapsed')
  const gridLabel = await evaluate(`Array.from(document.querySelectorAll('.layer-panel label')).findIndex(e=>e.textContent.includes('Priority grid'))`)
  assert.ok(gridLabel >= 0, 'Grid layer toggle must exist')
  await click('.layer-panel label', gridLabel)
  assert.equal(await evaluate('check.originalLayers.every(layer=>!layer._map)'), true)
  await click('.layer-panel label', gridLabel)
  assert.equal(await evaluate('check.originalLayers.every(layer=>!!layer._map)'), true)
  await click('.ranking-collapsed'); await click('.ranking-card'); await sleep(850)
  assert.match(await evaluate(`document.querySelector('.feature-panel h2').textContent`), /^Candidate Bus Stop #/)
  await click('.feature-identifier summary'); await click('.feature-identifier button'); await sleep(100)
  assert.match(await evaluate(`document.querySelector('.feature-identifier code').textContent`), /^baku:bus-stop-recommendation:/)
  assert.equal(await evaluate(`document.querySelector('.feature-identifier [role="status"]').textContent`), 'Copied')
  await click('.ranking-tabs button:nth-child(2)'); await click('.ranking-card'); await sleep(850)
  assert.match(await evaluate(`document.querySelector('.feature-panel h2').textContent`), /^Bicycle Corridor #/)
  assert.doesNotMatch(await evaluate(`document.querySelector('.feature-reasons').textContent`), /high_bike_priority_target/)
  await click('.ranking-collapse-button')
  await click('.analysis-collapse-button')
  await click('.summary-collapse-button')
  await click('.layer-panel-collapse')
  await click('.overview-view-button'); await sleep(900)
  for (const prefix of ['Bus stop ', 'Bus route ', 'Metro station ', 'Cycleway ', 'Candidate Bus Stop #', 'Bicycle Corridor #']) {
    await clickFeature(prefix)
  }
  await focus('path.keyboard-map-feature[aria-label^="Bus route "]')
  await key('Enter')
  assert.match(await evaluate(`document.querySelector('.feature-panel').innerText`), /Bus route/)
  await key(' ', 'Space')
  assert.match(await evaluate(`document.querySelector('.feature-panel').innerText`), /Bus route/)
  await key('Escape')
  // Release over other features and over empty space; neither may inspect.
  for (const to of [{x:1000,y:700},{x:1000,y:900},{x:500,y:700}]) {
    const point=await svgPoint('Bus route ')
    assert.ok(point)
    await evaluate('check.hitTests=0')
    await drag({x:point.x,y:point.y},to)
    assert.equal(await evaluate('check.hitTests'),0)
    assert.equal(await evaluate(`!!document.querySelector('.inspector-collapsed')`),true)
    await quietMap(); await viewportCoverage()
    await click('.overview-view-button'); await sleep(900)
  }
  await evaluate('check.hitTests=0;check.zoomEnds=0;check.map.on("zoomend",()=>check.zoomEnds++);void 0')
  for (let n=0;n<6;n++) {
    const before=await evaluate('check.zoomEnds')
    await call('Input.dispatchMouseEvent',{type:'mouseWheel',x:900,y:550,deltaX:0,deltaY:n%2===0?-80:80})
    let complete=false
    for(let wait=0;wait<80;wait++){
      await sleep(20)
      complete=await evaluate(`check.zoomEnds>${before} && !check.map._animatingZoom`)
      if(complete)break
    }
    assert.ok(complete)
    await settle(); await quietMap(); await viewportCoverage()
    assert.equal(await evaluate(`!!document.querySelector('.inspector-collapsed')`),true)
  }
  assert.equal(await evaluate('check.hitTests'),0,'Wheel zoom must not trigger hit tests')
  assert.equal(await evaluate('check.originalLayers.every((layer,i)=>layer.getLatLngs()===check.rings[i])'),true)
  await clickFeature('Candidate Bus Stop #')
  await snapshot('light-selection')
  const selectedId=await evaluate(`document.querySelector('.feature-identifier code').textContent`)
  await drag({x:900,y:600},{x:950,y:650})
  assert.equal(await evaluate(`document.querySelector('.feature-identifier code').textContent`),selectedId,'Dragging preserves explicit selection')
  await click('.theme-toggle')
  assert.equal(await evaluate(`document.querySelector('.app').dataset.theme`),'dark')
  await mouse({x:900,y:550}); await quietMap()
  await clickFeature('Bicycle Corridor #')
  await snapshot('dark-selection')
  await click('.theme-toggle')
  assert.equal(await evaluate(`document.querySelector('.app').dataset.theme`),'light')
  // Empty space at a nearby empty region clears the inspector on either theme.
  await key('Escape')
  for (const width of [320, 390, 768, 1024]) {
    await viewport(width, 844)
    await sleep(300); await viewportCoverage()
    assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true, `No horizontal overflow at ${width}px`)
    assert.equal(await evaluate(`[...document.querySelectorAll('aside')].every(e=>{const r=e.getBoundingClientRect();return r.left>=0 && r.right<=innerWidth})`), true)
  }
  await viewport(1440, 1000)
  await load('?qa=nulls')
  await click('.ranking-collapsed'); await click('.ranking-card')
  assert.match(await evaluate(`document.querySelector('.feature-panel').innerText`), /Unavailable/)
  await load('?qa=empty')
  await click('.ranking-collapsed')
  assert.match(await evaluate(`document.querySelector('.priority-ranking').innerText`), /No recommendations available/)
  await click('.grid-browser > button')
  assert.match(await evaluate(`document.querySelector('.grid-browser').innerText`), /0 matching cells/)
  assert.equal(exceptions.length, 0, JSON.stringify(exceptions))
  console.log(JSON.stringify({ passed: true, initial, metricMs, checks: 'All metric identities/colors; no hover tooltips/highlights/hit tests; all feature-type clicks; native keyboard + ranking + grid browser; drag/release + repeated wheel; viewport coverage; no reconstruction; selection halo/clear/Escape; themes; mobile; null/empty; no runtime exceptions' }, null, 2))
} finally {
  socket.close()
}
