import GridBrowser from './GridBrowser'
import { PRIORITY_EXPLANATION } from '../utils/presentation'
import { useState } from 'react'
import './AnalysisPanel.css'

const METRICS = {
  mobility_gap: {
    tab: 'Overall',
    title: 'Mobility gap',
    shortTitle: 'Overall gap',
    description:
      'Overall accessibility deficit across the analysis grid.',
  },

  bus_priority: {
    tab: 'Bus',
    title: 'Bus priority',
    shortTitle: 'Bus need',
    description:
      'Relative need for improved public-transport accessibility.',
  },

  bike_priority: {
    tab: 'Cycling',
    title: 'Bike priority',
    shortTitle: 'Cycling need',
    description:
      'Relative need for improved cycling accessibility.',
  },
}

const METRIC_ORDER = [
  'mobility_gap',
  'bus_priority',
  'bike_priority',
]

const SCALE_ITEMS = [
  {
    label: 'Low need',
    range: '0–24',
    className: 'analysis-scale-low',
  },
  {
    label: 'Moderate need',
    range: '25–49',
    className: 'analysis-scale-moderate',
  },
  {
    label: 'High need',
    range: '50–74',
    className: 'analysis-scale-high',
  },
  {
    label: 'Very high need',
    range: '75–100',
    className: 'analysis-scale-very-high',
  },
]

function AnalysisPanel({
  grid,
  onSelect,
  selectedMetric,
  onChange,
}) {
  const [collapsed, setCollapsed] =
    useState(false)

  const activeMetric =
    METRICS[selectedMetric] ??
    METRICS.mobility_gap

  if (collapsed) {
    return (
      <button
        type="button"
        className="analysis-collapsed"
        id="analysis-controls"
        onClick={() =>
          setCollapsed(false)
        }
        aria-label="Open analysis controls"
      >
        <span className="analysis-collapsed-icon">
          ◫
        </span>

        <span className="analysis-collapsed-copy">
          <strong>Analysis</strong>

          <span>
            {activeMetric.shortTitle}
          </span>
        </span>

        <span
          className="analysis-collapsed-arrow"
          aria-hidden="true"
        >
          ↑
        </span>
      </button>
    )
  }

  return (
    <aside className="analysis-panel" id="analysis-controls" tabIndex={-1}>
      <div className="analysis-header">
        <div>
          <p className="analysis-eyebrow">
            Accessibility analysis
          </p>

          <h2>Priority map</h2>

          <p className="analysis-intro">
            Choose which 0–100 score is
            displayed across the analysis
            grid.
          </p>
        </div>

        <button
          type="button"
          className="analysis-collapse-button"
          onClick={() =>
            setCollapsed(true)
          }
          aria-label="Collapse analysis controls"
        >
          ×
        </button>
      </div>

      <div
        className="analysis-tabs"
        role="group"
        aria-label="Analysis metric"
      >
        {METRIC_ORDER.map(
          (metricKey) => {
            const metric =
              METRICS[metricKey]

            const active =
              selectedMetric ===
              metricKey

            return (
              <button
                key={metricKey}
                type="button"
                aria-pressed={active}
                className={
                  active
                    ? 'active'
                    : ''
                }
                onClick={() =>
                  onChange(metricKey)
                }
              >
                {metric.tab}
              </button>
            )
          }
        )}
      </div>

      <section className="analysis-active-metric">
        <div className="analysis-active-heading">
          <div>
            <span>
              Current metric
            </span>

            <strong>
              {activeMetric.title}
            </strong>
          </div>

          <span className="analysis-score-badge">
            0–100
          </span>
        </div>

        <p>
          {activeMetric.description}
        </p>
      </section>

      <section className="analysis-section">
        <div className="analysis-section-heading">
          <span>
            Intervention need
          </span>

          <strong>
            Score scale
          </strong>
        </div>

        <div
          className="analysis-gradient"
          aria-hidden="true"
        />

        <div className="analysis-gradient-values">
          <span>0</span>
          <span>25</span>
          <span>50</span>
          <span>75</span>
          <span>100</span>
        </div>

        <div className="analysis-scale-list">
          {SCALE_ITEMS.map(
            (item) => (
              <div
                className="analysis-scale-row"
                key={item.range}
              >
                <span
                  className={`analysis-scale-swatch ${item.className}`}
                  aria-hidden="true"
                />

                <div>
                  <strong>
                    {item.label}
                  </strong>

                  <span>
                    {item.range}
                  </span>
                </div>
              </div>
            )
          )}

          <div className="analysis-scale-row">
            <span
              className="analysis-scale-swatch analysis-scale-unavailable"
              aria-hidden="true"
            />

            <div>
              <strong>
                Unavailable
              </strong>

              <span>
                Missing value
              </span>
            </div>
          </div>
        </div>
      </section>

      <div className="analysis-rule">
        <span
          className="analysis-rule-icon"
          aria-hidden="true"
        >
          ↑
        </span>

        <p>
          <strong>
            Higher score = greater
            intervention need.
          </strong>{' '}
          {PRIORITY_EXPLANATION}
        </p>
      </div>
      <GridBrowser grid={grid} selectedMetric={selectedMetric} onSelect={onSelect} />
    </aside>
  )
}

export default AnalysisPanel