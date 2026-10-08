import { useState } from 'react'
import './AnalysisPanel.css'

const METRICS = {
  mobility_gap: {
    label: 'Mobility Gap',
    shortLabel: 'Overall',
    description:
      'Overall accessibility deficit across the mobility system.',
  },
  bus_priority: {
    label: 'Bus Priority',
    shortLabel: 'Bus',
    description:
      'Need for bus and public-transport accessibility improvement.',
  },
  bike_priority: {
    label: 'Bike Priority',
    shortLabel: 'Cycling',
    description:
      'Need for cycling-access and first/last-mile improvement.',
  },
}

function AnalysisPanel({
  selectedMetric,
  onChange,
}) {
  const [collapsed, setCollapsed] = useState(false)

  const currentMetric =
    METRICS[selectedMetric] ?? METRICS.mobility_gap

  if (collapsed) {
    return (
      <button
        type="button"
        className="analysis-collapsed"
        onClick={() => setCollapsed(false)}
        aria-label="Open analysis controls"
      >
        <span className="analysis-collapsed-icon">
          ◈
        </span>

        <span className="analysis-collapsed-copy">
          <strong>Analysis</strong>
          <span>{currentMetric.label}</span>
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
    <aside className="analysis-panel">
      <div className="analysis-header">
        <div>
          <p className="analysis-eyebrow">
            Accessibility analysis
          </p>

          <h2>{currentMetric.label}</h2>
        </div>

        <button
          type="button"
          className="analysis-collapse-button"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse analysis controls"
        >
          ×
        </button>
      </div>

      <p className="analysis-description">
        {currentMetric.description}
      </p>

      <div
        className="analysis-tabs"
        role="tablist"
        aria-label="Analysis metric"
      >
        {Object.entries(METRICS).map(
          ([metricKey, metric]) => (
            <button
              type="button"
              key={metricKey}
              className={
                selectedMetric === metricKey
                  ? 'active'
                  : ''
              }
              onClick={() => onChange(metricKey)}
            >
              {metric.shortLabel}
            </button>
          )
        )}
      </div>

      <div className="analysis-scale-header">
        <span>Intervention need</span>
        <strong>0–100</strong>
      </div>

      <div className="analysis-gradient" />

      <div className="analysis-gradient-labels">
        <span>Lower</span>
        <span>Greater need</span>
      </div>

      <div className="analysis-legend">
        <div className="analysis-legend-row">
          <span className="analysis-swatch analysis-low" />
          <span>0–24</span>
          <strong>Low</strong>
        </div>

        <div className="analysis-legend-row">
          <span className="analysis-swatch analysis-moderate" />
          <span>25–49</span>
          <strong>Moderate</strong>
        </div>

        <div className="analysis-legend-row">
          <span className="analysis-swatch analysis-high" />
          <span>50–74</span>
          <strong>High</strong>
        </div>

        <div className="analysis-legend-row">
          <span className="analysis-swatch analysis-very-high" />
          <span>75–100</span>
          <strong>Very high</strong>
        </div>

        <div className="analysis-legend-row">
          <span className="analysis-swatch analysis-unavailable" />
          <span>—</span>
          <strong>Unavailable</strong>
        </div>
      </div>

      <p className="analysis-note">
        Higher score always means greater intervention need.
      </p>
    </aside>
  )
}

export default AnalysisPanel