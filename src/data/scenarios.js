const TYPES = { 'Bus recommendation': 'bus_stop', 'Bike recommendation': 'bike_corridor' }

export function createScenarioIndex(document) {
  return new Map((document?.scenarios ?? []).map(scenario => [scenario.intervention_id, scenario]))
}

export function findScenario(index, selection) {
  const expectedType = TYPES[selection?.type]
  if (!expectedType || typeof selection?.properties?.id !== 'string') return null
  const scenario = index.get(selection.properties.id)
  return scenario?.intervention_type === expectedType ? scenario : null
}
