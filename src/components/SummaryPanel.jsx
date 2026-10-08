function showValue(value) {
  if (value === null || value === undefined) {
    return 'Unavailable'
  }

  return value
}

function SummaryPanel({ summary }) {
  if (!summary) {
    return null
  }

  return (
    <section className="summary-panel">
      <h2>Mobility overview</h2>

      <div className="summary-grid">
        <div className="summary-card">
          <span className="summary-label">Grid cells</span>
          <strong>{showValue(summary.grid_cells)}</strong>
        </div>

        <div className="summary-card">
          <span className="summary-label">Population estimate</span>
          <strong>{showValue(summary.population_estimate)}</strong>
        </div>

        <div className="summary-card">
          <span className="summary-label">High bus priority</span>
          <strong>{showValue(summary.high_bus_priority_cells)}</strong>
        </div>

        <div className="summary-card">
          <span className="summary-label">High bike priority</span>
          <strong>{showValue(summary.high_bike_priority_cells)}</strong>
        </div>
      </div>
    </section>
  )
}

export default SummaryPanel