import { useState } from 'react'
import './LayerPanel.css'

function LayerSymbol({ type }) {
  return (
    <span
      className={`layer-symbol layer-symbol-${type}`}
      aria-hidden="true"
    >
      <span />
    </span>
  )
}

function LayerToggle({
  label,
  description,
  symbol,
  checked,
  onChange,
}) {
  return (
    <label className="layer-toggle">
      <LayerSymbol type={symbol} />

      <div className="layer-toggle-copy">
        <strong>{label}</strong>
        <span>{description}</span>
      </div>

      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
      />

      <span
        className="layer-switch"
        aria-hidden="true"
      >
        <span />
      </span>
    </label>
  )
}

function LayerPanel({
  visibility,
  onToggle,
}) {
  const [collapsed, setCollapsed] =
    useState(true)

  if (collapsed) {
    return (
      <button
        type="button"
        className="layers-collapsed"
        onClick={() =>
          setCollapsed(false)
        }
        aria-label="Open map layers"
      >
        <span className="layers-collapsed-icon">
          ≡
        </span>

        <span className="layers-collapsed-copy">
          <strong>Map layers</strong>
          <span>
            Infrastructure & analysis
          </span>
        </span>

        <span
          className="layers-collapsed-arrow"
          aria-hidden="true"
        >
          ↑
        </span>
      </button>
    )
  }

  return (
    <aside className="layer-panel">
      <div className="layer-panel-header">
        <div>
          <p className="layer-panel-eyebrow">
            Map display
          </p>

          <h2>Layers</h2>

          <p className="layer-panel-intro">
            Existing infrastructure,
            analysis and proposed
            interventions.
          </p>
        </div>

        <button
          type="button"
          className="layer-panel-collapse"
          onClick={() =>
            setCollapsed(true)
          }
          aria-label="Collapse map layers"
        >
          ×
        </button>
      </div>

      <section className="layer-section">
        <div className="layer-section-heading">
          <span className="layer-section-status layer-section-existing">
            Existing
          </span>

          <p className="layer-section-title">
            Infrastructure
          </p>
        </div>

        <LayerToggle
          label="Bus stops"
          description="Existing stop locations"
          symbol="bus-stop"
          checked={visibility.busStops}
          onChange={() =>
            onToggle('busStops')
          }
        />

        <LayerToggle
          label="Bus routes"
          description="Existing route geometry"
          symbol="bus-route"
          checked={visibility.busRoutes}
          onChange={() =>
            onToggle('busRoutes')
          }
        />

        <LayerToggle
          label="Metro stations"
          description="Existing metro access"
          symbol="metro"
          checked={
            visibility.metroStations
          }
          onChange={() =>
            onToggle('metroStations')
          }
        />

        <LayerToggle
          label="Cycleways"
          description="Existing cycling infrastructure"
          symbol="cycleway"
          checked={visibility.cycleways}
          onChange={() =>
            onToggle('cycleways')
          }
        />
      </section>

      <section className="layer-section">
        <div className="layer-section-heading">
          <span className="layer-section-status layer-section-analysis">
            Analysis
          </span>

          <p className="layer-section-title">
            Accessibility
          </p>
        </div>

        <LayerToggle
          label="Priority grid"
          description="Current selected analysis score"
          symbol="grid"
          checked={visibility.grid}
          onChange={() =>
            onToggle('grid')
          }
        />
      </section>

      <section className="layer-section">
        <div className="layer-section-heading">
          <span className="layer-section-status layer-section-proposed">
            Proposed
          </span>

          <p className="layer-section-title">
            Improvements
          </p>
        </div>

        <LayerToggle
          label="Candidate bus improvements"
          description="Public-transport interventions"
          symbol="bus-recommendation"
          checked={
            visibility.busRecommendations
          }
          onChange={() =>
            onToggle(
              'busRecommendations'
            )
          }
        />

        <LayerToggle
          label="Candidate bicycle corridors"
          description="Further engineering assessment"
          symbol="bike-recommendation"
          checked={
            visibility.bikeRecommendations
          }
          onChange={() =>
            onToggle(
              'bikeRecommendations'
            )
          }
        />
      </section>

      <div className="layer-panel-note">
        <span aria-hidden="true">
          ◇
        </span>

        <p>
          Proposed bicycle corridors are
          candidates for further engineering
          assessment.
        </p>
      </div>
    </aside>
  )
}

export default LayerPanel