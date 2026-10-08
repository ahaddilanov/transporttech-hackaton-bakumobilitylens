import { useState } from 'react'

function showValue(value) {
  if (value === null || value === undefined) {
    return 'Unavailable'
  }

  return value
}

function SummaryPanel({ summary }) {
  const [collapsed, setCollapsed] = useState(false)

  if (!summary) {
    return null
  }

  if (collapsed) {
    return (
      <button
        type="button"
        className="summary-collapsed"
        onClick={() => setCollapsed(false)}
        aria-label="Open mobility overview"
      >
        <span className="summary-collapsed-icon">
          ◫
        </span>

        <span className="summary-collapsed-copy">
          <strong>Overview</strong>
          <span>Baku mobility summary</span>
        </span>

        <span
          className="summary-collapsed-arrow"
          aria-hidden="true"
        >
          ↓
        </span>
      </button>
    )
  }

  return (
    <section className="summary-panel">
      <div className="summary-header">
        <div>
          <p className="summary-eyebrow">
            City snapshot
          </p>

          <h2>Mobility overview</h2>
        </div>

        <button
          type="button"
          className="summary-collapse-button"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse mobility overview"
        >
          ×
        </button>
      </div>

      <div className="summary-grid">
        <div className="summary-card">
          <span className="summary-label">
            Grid cells
          </span>

          <strong>
            {showValue(summary.grid_cells)}
          </strong>
        </div>

        <div className="summary-card">
          <span className="summary-label">
            Population estimate
          </span>

          <strong>
            {showValue(summary.population_estimate)}
          </strong>
        </div>

        <div className="summary-card">
          <span className="summary-label">
            High bus priority
          </span>

          <strong>
            {showValue(
              summary.high_bus_priority_cells
            )}
          </strong>
        </div>

        <div className="summary-card">
          <span className="summary-label">
            High bike priority
          </span>

          <strong>
            {showValue(
              summary.high_bike_priority_cells
            )}
          </strong>
        </div>
      </div>
    </section>
  )
}

export default SummaryPanel