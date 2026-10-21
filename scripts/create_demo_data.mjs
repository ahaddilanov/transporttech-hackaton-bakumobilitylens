// Original, hand-authored UI examples. No real datasets are read by this script.
// Only demo/public/data is written; public/data is never used as an output.
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

export function createDemoData() {
  const metadata = {
    synthetic: true,
    source: 'Original hand-authored Baku Mobility Lens UI fixture',
    limitations: ['Made-up coordinates and values; not real infrastructure, residents, routing or analysis results.'],
  }
  const feature = (id, geometry, properties) => ({
    type: 'Feature', id, geometry, properties: { id, ...properties, source: 'Synthetic example' },
  })
  const point = coordinates => ({ type: 'Point', coordinates })
  const line = coordinates => ({ type: 'LineString', coordinates })
  const collection = features => ({ type: 'FeatureCollection', metadata, features })
  // Rectangles and lines invented numerically near the map's initial view.
  // These coordinates do not trace any supplied road, lane, stop or boundary.
  const grid = [100, 200, 0, null].map((population, i) => {
    const x = 49.85 + (i % 2) * 0.008
    const y = 40.41 + Math.floor(i / 2) * 0.006
    return feature(`synthetic:grid:${i + 1}`, { type: 'Polygon', coordinates: [
      [[x, y], [x + 0.007, y], [x + 0.007, y + 0.005], [x, y + 0.005], [x, y]],
    ] }, {
      population, nearest_bus_stop_m: [800, 200, 1200, 900][i],
      nearest_metro_m: 1500, nearest_cycleway_m: [900, 800, 0, 650][i],
      bus_stops_500m: i === 1 ? 1 : 0, bus_routes_nearby: 1, pois_nearby: 0,
      bus_priority: [80, 65, 0, null][i], bike_priority: [70, 90, 0, null][i],
      mobility_gap: [75, 80, 0, null][i],
    })
  })
  const reason = ['Synthetic UI example; not a real infrastructure proposal.']
  const bus = feature('synthetic:bus:1', point([49.854, 40.413]), {
    priority: 80, population_affected: 100, current_access_m: 800,
    new_access_m: 100, access_improvement_m: 700, reason,
  })
  const bike = feature('synthetic:bike:1', line([[49.856, 40.412], [49.862, 40.419]]), {
    priority: 90, length_m: 950, population_coverage_gain: 200,
    start_name: 'Synthetic connection A', end_name: 'Synthetic destination B', reason,
  })
  const scenario = (id, type, newlyCovered, before, after, improvement) => ({
    intervention_id: id, intervention_type: type, population_improved: 300,
    coverage_before_pct: before, coverage_after_pct: after,
    coverage_change_pp: after - before, avg_access_improvement_m: improvement,
    affected_cells: 2, newly_covered_population: newlyCovered, newly_covered_cells: 1,
    unknown_population_cells_affected: 1, model_version: 'synthetic-ui-example-v1',
    coverage_radius_m: 500,
    reconciliation: { status: 'match', recommendation_value: newlyCovered,
      simulation_value: newlyCovered, difference_population: 0 },
  })
  return {
    'grid.geojson': collection(grid),
    'bus_stops.geojson': collection([
      feature('synthetic:stop:1', point([49.86, 40.413]), { name: 'Synthetic stop A' }),
      feature('synthetic:stop:2', point([49.865, 40.42]), { name: null }),
    ]),
    'bus_routes.geojson': collection([feature('synthetic:route:1',
      line([[49.848, 40.409], [49.854, 40.413], [49.867, 40.42]]),
      { name: 'Synthetic route', route_ref: 'DEMO', avg_daily_validations: null })]),
    'metro_stations.geojson': collection([feature('synthetic:metro:1', point([49.866, 40.41]),
      { name: 'Synthetic station', avg_daily_entries: null })]),
    'cycleways.geojson': collection([feature('synthetic:lane:1', line([[49.85, 40.419], [49.856, 40.419]]),
      { name: 'Synthetic existing lane', length_m: 510 })]),
    'bus_recommendations.geojson': collection([bus]),
    'bike_recommendations.geojson': collection([bike]),
    'summary.json': {
      ...metadata, generated_at: '2026-01-01T00:00:00Z', grid_cells: grid.length,
      population_estimate: 300, high_bus_priority_cells: 2, high_bike_priority_cells: 2,
    },
    'intervention_scenarios.json': {
      metadata: { ...metadata, coverage_radius_m: 500 },
      summary: { synthetic: true, total_scenarios: 2 },
      scenarios: [scenario(bus.id, 'bus_stop', 100, 200 / 3, 100, 250),
        scenario(bike.id, 'bike_corridor', 200, 0, 200 / 3, 400)],
    },
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const directory = new URL('../demo/public/data/', import.meta.url)
  await mkdir(directory, { recursive: true })
  for (const [name, data] of Object.entries(createDemoData())) {
    await writeFile(new URL(name, directory), `${JSON.stringify(data, null, 2)}\n`)
  }
  process.stdout.write('Wrote 9 synthetic UI fixtures to demo/public/data only.\n')
}
