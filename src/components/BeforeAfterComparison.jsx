import { showValue, showPercentage, showPercentagePoints } from '../utils/presentation'
import './BeforeAfterComparison.css'

const STATUS_LABELS = {
  match: 'Matches recommendation estimate',
  unavailable: 'Recommendation comparison unavailable',
  consistent_with_osm_exclusion: 'Consistent with OSM exclusions',
}

function Metric({ label, value, field }) {
  return <div><dt>{label}</dt><dd data-scenario-field={field}>{value}</dd></div>
}

export default function BeforeAfterComparison({ scenario, status }) {
  const reconciliation = scenario?.reconciliation
  return (
    <details className="simulation-comparison">
      <summary>Before / After accessibility</summary>
      {!scenario ? (
        <p className="simulation-note" role="status">
          {status === 'loading' ? 'Loading saved accessibility scenario…'
            : status === 'unavailable' ? 'Saved simulation data is unavailable. Recommendation details remain available.'
              : 'No saved simulation matches this recommendation’s full ID and intervention type.'}
        </p>
      ) : (
        <>
          <p className="simulation-note">Hypothetical straight-line accessibility estimates for this intervention alone, using a 500 m coverage threshold.</p>
          <dl className="simulation-metrics">
            <Metric label="Coverage before" field="coverage_before_pct" value={showPercentage(scenario.coverage_before_pct)} />
            <Metric label="Coverage after" field="coverage_after_pct" value={showPercentage(scenario.coverage_after_pct)} />
            <Metric label="Coverage change (percentage points)" field="coverage_change_pp" value={showPercentagePoints(scenario.coverage_change_pp)} />
            <Metric label="Population newly within 500 m" field="newly_covered_population" value={showValue(scenario.newly_covered_population)} />
            <Metric label="Population with improved proximity" field="population_improved" value={showValue(scenario.population_improved)} />
            <Metric label="Average access improvement" field="avg_access_improvement_m" value={showValue(scenario.avg_access_improvement_m, ' m')} />
          </dl>
          <p className="simulation-note">Newly covered residents cross from more than 500 m to within 500 m. Improved proximity includes any modeled distance reduction, even for residents already covered or still farther than 500 m away. Average improvement is population-weighted over improved residents.</p>
          <p className="simulation-note">Coverage percentages use the same full-grid known-population denominator. Population estimates are rounded; cells with unknown population are excluded from those estimates.</p>
          {scenario.unknown_population_cells_affected != null && (
            <p className="simulation-note">{showValue(scenario.unknown_population_cells_affected)} cells with unknown population also have improved proximity; their residents are not included in the population totals.</p>
          )}
          {scenario.intervention_type === 'bike_corridor' && (
            <p className="simulation-note simulation-baseline">Cycling baseline: mapped AYNA bicycle lanes only. Recommendation estimates additionally exclude cells within 500 m of classified existing OSM cycling infrastructure. The simulation keeps the AYNA-only baseline.</p>
          )}
          {reconciliation && (
            <div className="simulation-reconciliation" data-reconciliation-status={reconciliation.status}>
              <h3>{STATUS_LABELS[reconciliation.status]}</h3>
              {reconciliation.status === 'consistent_with_osm_exclusion' && (
                <>
                  <dl className="simulation-metrics">
                    <Metric label="Recommendation: newly covered population" field="recommendation_value" value={showValue(reconciliation.recommendation_value)} />
                    <Metric label="AYNA-only simulation: newly covered population" field="simulation_value" value={showValue(reconciliation.simulation_value)} />
                  </dl>
                  <p className="simulation-note">These estimates differ because the recommendation applies the additional OSM exclusions. {reconciliation.osm_gate_recomputed_by_simulator === false
                    ? 'The saved reconciliation checks aggregate consistency; the simulator did not independently recheck which cells were excluded.'
                    : 'See the recorded methodology note for how the exclusions were assessed.'}</p>
                  {reconciliation.explanation && (
                    <details className="simulation-method-note"><summary>Recorded methodology note</summary><p className="simulation-note">{reconciliation.explanation}</p></details>
                  )}
                </>
              )}
            </div>
          )}
          <p className="simulation-note">Each scenario starts from the unchanged baseline. Separate proposals may benefit the same residents; do not add their gains into a combined citywide improvement. These are not ridership forecasts or approved engineering outcomes.</p>
        </>
      )}
    </details>
  )
}
