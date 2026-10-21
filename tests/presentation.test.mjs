import test from 'node:test'
import assert from 'node:assert/strict'
import { showValue, showScore, readableReason, recommendationLabels } from '../src/utils/presentation.js'

test('population estimates round for display and preserve zero versus unknown', () => {
  assert.equal(showValue(2898185.147), '2,898,185')
  assert.equal(showValue(0), '0')
  for (const value of [null, undefined, NaN, Infinity]) assert.equal(showValue(value), 'Unavailable')
})

test('distance units and precision are readable at either side of 1 km', () => {
  assert.equal(showValue(662.198, ' m'), '662 m')
  assert.equal(showValue(1020.232, ' m'), '1.02 km')
  assert.equal(showValue(1000, ' m'), '1 km')
  assert.equal(showValue(0, ' m'), '0 m')
  assert.equal(showValue(null, ' m'), 'Unavailable')
  assert.equal(showScore(100), '100/100')
  assert.equal(showScore(null), 'Unavailable')
})

test('known reasons are readable and unknown source text is retained', () => {
  assert.equal(readableReason('high_bus_priority_seed'), 'Starts from an area with high bus intervention need.')
  assert.equal(readableReason('A future reason'), 'A future reason')
})

test('short recommendation labels keep complete IDs and source order without mutation', () => {
  const bus = { features: [{ properties: { id: 'bus-long-hash-A', priority: 60 } }, { properties: { id: 'bus-long-hash-B', priority: 100 } }] }
  const bike = { features: [{ properties: { id: 'bike-long-hash-C', priority: 90 } }] }
  const before = JSON.stringify({ bus, bike })
  const labels = recommendationLabels(bus, bike)
  assert.equal(labels.get('bus-long-hash-A'), 'Candidate Bus Stop #1')
  assert.equal(labels.get('bus-long-hash-B'), 'Candidate Bus Stop #2')
  assert.equal(labels.get('bike-long-hash-C'), 'Bicycle Corridor #1')
  assert.deepEqual(recommendationLabels(bus, bike), labels)
  assert.equal(JSON.stringify({ bus, bike }), before)
  assert.equal(recommendationLabels(null, null).size, 0)
})
