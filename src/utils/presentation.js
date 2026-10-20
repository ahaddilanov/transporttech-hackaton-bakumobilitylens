// Display formatting only: source properties, scores and simulation values stay intact.
const whole = new Intl.NumberFormat('en', { maximumFractionDigits: 0 })
const kilometres = new Intl.NumberFormat('en', { maximumFractionDigits: 2 })

export function showValue(value, suffix = '') {
  if (value === null || value === undefined ||
      (typeof value === 'number' && !Number.isFinite(value))) return 'Unavailable'
  if (typeof value !== 'number') return `${value}${suffix}`
  if (suffix === ' m') {
    return Math.abs(value) >= 1000
      ? `${kilometres.format(value / 1000)} km`
      : `${whole.format(value)} m`
  }
  return `${whole.format(value)}${suffix}`
}

export function showScore(value) {
  return value === null || value === undefined ? 'Unavailable' : `${showValue(value)}/100`
}

const REASONS = {
  at_least_300m_from_mapped_existing_stop: 'At least 300 m from a mapped existing bus stop.',
  high_bus_priority_seed: 'Starts from an area with high bus intervention need.',
  positive_modeled_population_gain_within_500m: 'Would bring additional modeled residents within 500 m of a bus stop.',
  preliminary_requires_field_and_engineering_assessment: 'Preliminary proposal requiring field and engineering assessment.',
  projected_onto_nearest_AYNA_route_geometry: 'Located on the nearest mapped AYNA route. This does not establish stop permission or route membership.',
  at_least_200m_proposed_new_infrastructure: 'Includes at least 200 m of proposed new cycling infrastructure.',
  directed_path_from_AYNA_proximity_anchor: 'Follows permitted travel directions from a network point near an AYNA bicycle lane.',
  high_bike_priority_target: 'Connects toward an area with high cycling intervention need.',
  positive_modeled_population_gain: 'Would extend cycling access to additional modeled residents.',
}

export function readableReason(reason) {
  return REASONS[reason] ?? reason
}

// Number within each source dataset, independent of ranking, filtering or selection.
export function recommendationLabels(bus, bike) {
  return new Map([
    ...(bus?.features ?? []).map((f, i) => [f.properties.id, `Candidate Bus Stop #${i + 1}`]),
    ...(bike?.features ?? []).map((f, i) => [f.properties.id, `Bicycle Corridor #${i + 1}`]),
  ])
}

export const PRIORITY_EXPLANATION = '100/100 indicates the highest modeled intervention need, not certainty, safety or approval.'
