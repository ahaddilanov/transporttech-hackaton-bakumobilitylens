// Four reproducible real-wheel comparisons on the actual datasets. No dependencies.
import assert from 'node:assert/strict'
import { writeFile } from 'node:fs/promises'
import { socket, call, evaluate, sleep, settle, load, click, viewport } from './browser-client.mjs'
const rounds = Number(process.env.ZOOM_ROUNDS ?? 3)
assert.ok(Number.isInteger(rounds) && rounds >= 1 && rounds <= 10)
try {
  await call('Page.enable')
  await call('Runtime.enable')
  await call('Network.enable')
  await call('Network.setBlockedURLs', { urls: ['*tile.openstreetmap.org*'] })
  await viewport(1440, 1000)
  await load()
  await evaluate(`(async () => {
    const url=performance.getEntriesByType('resource').find(e=>e.name.includes('/deps/leaflet.js')).name;
    const L=(await import(url)).default;
    window.profile={L,layers:[],samples:[],ends:0};
    const original=L.Path.prototype.setStyle;
    profile.originalStyle=original;
    L.Path.prototype.setStyle=function(style){if(this.feature?.properties?.mobility_gap!==undefined)profile.layers.push(this);return original.call(this,style)};
  })()`)
  await click('.analysis-tabs button:nth-child(2)')
  await evaluate(`(() => {
    const p=profile;
    p.L.Path.prototype.setStyle=p.originalStyle;
    p.map=p.layers.find(layer=>layer._map)._map;
    p.allGridLayers=p.layers[0]._eventParents[Object.keys(p.layers[0]._eventParents)[0]].getLayers();
    p.restores=[];
    const measure=(name,fn,context,args)=>{
      const started=performance.now();
      try{return fn.apply(context,args)}finally{p.samples.push({name,ms:performance.now()-started})}
    };
    const wrap=(object,key,name)=>{
      const original=object[key];
      object[key]=function(...args){return measure(name,original,this,args)};
      p.restores.push(()=>object[key]=original);
    };
    for(const renderer of Object.values(p.map._layers).filter(layer=>layer instanceof p.L.Renderer)){
      const name=renderer.options.pane;
      for(const type of ['zoomend','moveend','viewreset']){
        for(const listener of p.map._events[type]??[]){
          if(listener.ctx===renderer)wrap(listener,'fn',name+':'+type);
        }
      }
      for(const listener of renderer._events.update??[])wrap(listener,'fn',name+':updatePaths');
      if(renderer instanceof p.L.Canvas){wrap(renderer,'_draw',name+':draw');wrap(renderer,'_handleMouseHover',name+':hover');}
    }
    p.map.on('zoomend',()=>{p.ends++;p.lastZoomEnd=performance.now()});
  })()`)
  await click('.analysis-collapse-button')
  await click('.summary-collapse-button')
  await click('.layers-collapsed')
  const labels = await evaluate(`[...document.querySelectorAll('.layer-panel label')].map(e=>e.textContent)`)
  const gridIndex = labels.findIndex(s=>s.includes('Priority grid'))
  const routesIndex = labels.findIndex(s=>s.includes('Bus routes'))
  assert.ok(gridIndex >= 0 && routesIndex >= 0)
  let grid = true, routes = true
  const results = []
  for (const config of [{grid:true,routes:true},{grid:false,routes:true},{grid:true,routes:false},{grid:false,routes:false}]) {
    if(grid!==config.grid){await click('.layer-panel label',gridIndex);grid=config.grid}
    if(routes!==config.routes){await click('.layer-panel label',routesIndex);routes=config.routes}
    await click('.overview-view-button'); await sleep(1000); await settle()
    await evaluate('profile.samples=[]')
    const samples = []
    for(let i=0;i<rounds*2;i++){
      const before = await evaluate('({ends:profile.ends,zoom:profile.map.getZoom(),started:performance.now()})')
      await call('Input.dispatchMouseEvent',{type:'mouseWheel',x:900,y:550,deltaX:0,deltaY:i%2===0?-80:80})
      let completed=false
      for(let n=0;n<100;n++){
        await sleep(20)
        completed=await evaluate(`profile.ends>${before.ends} && !profile.map._animatingZoom`)
        if(completed)break
      }
      assert.ok(completed,'Wheel zoom must finish')
      await settle()
      samples.push(await evaluate(`({settleMs:performance.now()-${before.started},zoom:profile.map.getZoom(),activeGridLayers:profile.allGridLayers.filter(layer=>!!layer._map).length,renderedGridLayers:profile.allGridLayers.find(layer=>layer._map)?._renderer._visibleLayers?.length ?? null})`))
      await sleep(100)
    }
    const totals = await evaluate(`profile.samples.reduce((result,sample)=>{
      const metric=result[sample.name]??={calls:0,totalMs:0,maxMs:0};
      metric.calls++;metric.totalMs+=sample.ms;metric.maxMs=Math.max(metric.maxMs,sample.ms);return result;
    },{})`)
    const sorted=samples.map(s=>s.settleMs).sort((a,b)=>a-b)
    results.push({...config,medianSettleMs:(sorted[Math.floor((sorted.length-1)/2)]+sorted[Math.ceil((sorted.length-1)/2)])/2,samples,totals})
  }
  const output={viewport:'1440x1000, dpr=1',tiles:'blocked to isolate vectors',wheel:'alternating deltaY -80/+80 at (900,550), zoom 12 reset for each case',rounds,results}
  console.log(JSON.stringify(output,null,2))
  if(process.argv[2])await writeFile(process.argv[2],JSON.stringify(output,null,2)+'\n')
} finally { socket.close() }
