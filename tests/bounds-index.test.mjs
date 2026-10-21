import test from 'node:test'
import assert from 'node:assert/strict'
import { createBoundsIndex } from '../src/utils/boundsIndex.js'

test('viewport search retains intersecting boundary cells and original object identity', () => {
  const cells = [
    { id: 'a', bounds: [49.8, 40.3, 49.81, 40.31] },
    { id: 'b', bounds: [49.81, 40.31, 49.82, 40.32] },
    { id: 'wide', bounds: [49.7, 40.2, 50.1, 40.6] },
  ]
  const before = JSON.stringify(cells)
  const index = createBoundsIndex(cells, cell => cell.bounds)
  const found = index.search([49.81, 40.31, 49.815, 40.315])
  assert.deepEqual(found, cells)
  assert.equal(found[2], cells[2])
  assert.equal(JSON.stringify(cells), before)
  assert.deepEqual(index.search([45, 30, 46, 31]), [])
  assert.deepEqual(index.search([-180, -90, 180, 90]), cells)
})

test('indexed answers match exhaustive geometric bounds checks for varied viewports', () => {
  const cells = Array.from({ length: 400 }, (_, i) => ({
    id: i, bounds: [49.5 + (i % 20) * 0.004, 40.1 + Math.floor(i / 20) * 0.003,
      49.505 + (i % 20) * 0.004, 40.104 + Math.floor(i / 20) * 0.003],
  }))
  const index = createBoundsIndex(cells, cell => cell.bounds)
  for (let i = 0; i < 100; i++) {
    const west = 49.48 + (i % 10) * 0.012
    const south = 40.08 + Math.floor(i / 10) * 0.009
    const east = west + 0.025
    const north = south + 0.018
    const expected = cells.filter(({ bounds: b }) => !(b[2] < west || b[0] > east || b[3] < south || b[1] > north))
    assert.deepEqual(index.search([west, south, east, north]), expected)
  }
  assert.deepEqual(createBoundsIndex([], cell => cell.bounds).search([-180, -90, 180, 90]), [])
})
