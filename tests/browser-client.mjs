// Shared dependency-free CDP client for the isolated local test browser.
import assert from 'node:assert/strict'
const base = process.env.APP_URL ?? 'http://127.0.0.1:5173/'
const debuggerUrl = process.env.CHROME_DEBUG_URL ?? 'http://127.0.0.1:9222'
const pages = await (await fetch(`${debuggerUrl}/json`)).json()
const page = pages.find(p => p.type === 'page' && (p.url === 'about:blank' || p.url.startsWith(base)))
assert.ok(page, 'Start an isolated Chrome profile with an about:blank tab')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }))
let sequence = 0
const pending = new Map()
const exceptions = []
socket.addEventListener('message', event => {
  const message = JSON.parse(event.data)
  if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails)
  if (!message.id) return
  const request = pending.get(message.id)
  pending.delete(message.id)
  clearTimeout(request.timer)
  if (message.error) request.reject(new Error(JSON.stringify(message.error)))
  else request.resolve(message.result)
})
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence
    const timer = setTimeout(() => reject(new Error(`Timed out: ${method}`)), 30000)
    pending.set(id, { resolve, reject, timer })
    socket.send(JSON.stringify({ id, method, params }))
  })
}
async function evaluate(expression) {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  assert.equal(result.exceptionDetails, undefined, JSON.stringify(result.exceptionDetails))
  return result.result.value
}
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
async function settle() {
  await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
}
async function load(query = '') {
  await call('Page.navigate', { url: `${base}${query}` })
  let ready = false
  for (let n = 0; n < 100; n++) {
    await sleep(200)
    ready = await evaluate(`!!document.querySelector('.analysis-panel') && !document.querySelector('.data-status-stack')`)
    if (ready) break
  }
  assert.ok(ready, 'Datasets must finish loading without errors')
  await settle()
}
async function click(selector, index = 0) {
  const point = await evaluate(`(() => {
    const element = document.querySelectorAll(${JSON.stringify(selector)})[${index}];
    element.scrollIntoView({block:'nearest'});
    const rect = element.getBoundingClientRect();
    return {x:rect.x+rect.width/2,y:rect.y+rect.height/2};
  })()`)
  await mouse(point, true)
  await settle()
}
async function mouse(point, click = false) {
  await call('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
  if (click) {
    await call('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', clickCount: 1, ...point })
    await call('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', clickCount: 1, ...point })
  }
}
async function focus(selector) {
  const { root } = await call('DOM.getDocument')
  const { nodeId } = await call('DOM.querySelector', { nodeId: root.nodeId, selector })
  await call('DOM.focus', { nodeId })
}
async function key(key, code = key) {
  await call('Input.dispatchKeyEvent', { type: 'keyDown', key, code, text: key === 'Enter' ? '\r' : key === ' ' ? ' ' : '', windowsVirtualKeyCode: { Enter: 13, Escape: 27, ' ': 32, Tab: 9 }[key] })
  await call('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: { Enter: 13, Escape: 27, ' ': 32, Tab: 9 }[key] })
  await settle()
}
async function viewport(width, height) {
  await call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false })
  await sleep(150)
}

export { base, socket, exceptions, call, evaluate, sleep, settle, load, click, mouse, focus, key, viewport }
