import { useState } from 'react'
import './SummaryPanel.css'

function showNumber(value) {
  if (value === null || value === undefined) {
    return 'Unavailable'
  }

  if (typeof value === 'number') {
    return value.toLocaleString()
  }

  return value
}

function formatGeneratedAt(value) {
  if (!value) {
    return 'Unavailable'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Unavailable'
  }

  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function SummaryMetric({
  label,
  value,
  description,
  emphasis = 'neutral',
}) {
  return (
    <div
      className={`summary-metric summary-metric-${emphasis}`}
    >
      <div className="summary-metric-top">
        <span className="summary-metric-label">
          {label}
        </span>

        <span
          className="summary-metric-dot"
          aria-hidden="true"
        />
      </div>

      <strong className="summary-metric-value">
        {value}
      </strong>

      <span className="summary-metric-description">
        {description}
      </span>
    </div>
  )
}

function SummaryPanel({ summary }) {
  const [collapsed, setCollapsed] =
    useState(false)

  if (!summary) {
    return null
  }

  if (collapsed) {
    return (
      <button
        type="button"
        className="summary-collapsed"
        onClick={() =>
          setCollapsed(false)
        }
        aria-label="Open mobility overview"
      >
        <span className="summary-collapsed-icon">
          ◫
        </span>

        <span className="summary-collapsed-copy">
          <strong>
            Mobility overview
          </strong>

          <span>
            Baku city snapshot
          </span>
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
        <div className="summary-heading">
          <p className="summary-eyebrow">
            City snapshot
          </p>

          <h2>
            Mobility overview
          </h2>

          <p className="summary-subtitle">
            Current accessibility and
            intervention-priority summary.
          </p>
        </div>

        <button
          type="button"
          className="summary-collapse-button"
          onClick={() =>
            setCollapsed(true)
          }
          aria-label="Collapse mobility overview"
        >
          ×
        </button>
      </div>

      <div className="summary-grid">
        <SummaryMetric
          label="Population"
          value={showNumber(
            summary.population_estimate
          )}
          description="Estimated population represented"
          emphasis="population"
        />

        <SummaryMetric
          label="Analysis cells"
          value={showNumber(
            summary.grid_cells
          )}
          description="Grid cells included in analysis"
          emphasis="grid"
        />

        <SummaryMetric
          label="High bus need"
          value={showNumber(
            summary.high_bus_priority_cells
          )}
          description="Cells with high bus intervention priority"
          emphasis="bus"
        />

        <SummaryMetric
          label="High cycling need"
          value={showNumber(
            summary.high_bike_priority_cells
          )}
          description="Cells with high cycling intervention priority"
          emphasis="bike"
        />
      </div>

      <div className="summary-footer">
        <div className="summary-footer-status">
          <span
            className="summary-status-dot"
            aria-hidden="true"
          />

          <span>
            Higher priority means greater
            intervention need
          </span>
        </div>

        <div className="summary-generated">
          <span>
            Generated
          </span>

          <strong>
            {formatGeneratedAt(
              summary.generated_at
            )}
          </strong>
        </div>
      </div>
    </section>
  )
}

export default SummaryPanel