// Uniform geographic buckets for Baku's small grid cells. Bounding boxes only
// choose render candidates; full original polygons still draw and handle clicks.
export function createBoundsIndex(items, getBounds, bucketSize = 0.02) {
  const buckets = new Map()
  const records = items.map((item, order) => ({ item, order, bounds: getBounds(item) }))
  if (!records.length) return { search: () => [] }
  const extent = [Infinity, Infinity, -Infinity, -Infinity]
  for (const record of records) {
    const [west, south, east, north] = record.bounds
    extent[0] = Math.min(extent[0], west)
    extent[1] = Math.min(extent[1], south)
    extent[2] = Math.max(extent[2], east)
    extent[3] = Math.max(extent[3], north)
    for (let x = Math.floor(west / bucketSize); x <= Math.floor(east / bucketSize); x++) {
      for (let y = Math.floor(south / bucketSize); y <= Math.floor(north / bucketSize); y++) {
        const key = `${x}:${y}`
        if (!buckets.has(key)) buckets.set(key, [])
        buckets.get(key).push(record)
      }
    }
  }
  return {
    search([west, south, east, north]) {
      if (west > extent[2] || east < extent[0] || south > extent[3] || north < extent[1]) return []
      const candidates = new Set()
      // Clamping also bounds the work when the user zooms out to a world view.
      for (let x = Math.floor(Math.max(west, extent[0]) / bucketSize); x <= Math.floor(Math.min(east, extent[2]) / bucketSize); x++) {
        for (let y = Math.floor(Math.max(south, extent[1]) / bucketSize); y <= Math.floor(Math.min(north, extent[3]) / bucketSize); y++) {
          for (const record of buckets.get(`${x}:${y}`) ?? []) {
            const b = record.bounds
            if (b[0] <= east && b[2] >= west && b[1] <= north && b[3] >= south) candidates.add(record)
          }
        }
      }
      return [...candidates].sort((a, b) => a.order - b.order).map(record => record.item)
    },
  }
}
