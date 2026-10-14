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
            Real baseline infrastructure
            and accessibility analysis.
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
          description="Mapped OSM stop locations"
          symbol="bus-stop"
          checked={visibility.busStops}
          onChange={() =>
            onToggle('busStops')
          }
        />

        <LayerToggle
          label="Bus routes"
          description="AYNA route geometry"
          symbol="bus-route"
          checked={visibility.busRoutes}
          onChange={() =>
            onToggle('busRoutes')
          }
        />

        <LayerToggle
          label="Metro stations"
          description="Metro station locations"
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
          description="Mapped bicycle-lane features"
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
          description="Current selected 0–100 need score"
          symbol="grid"
          checked={visibility.grid}
          onChange={() =>
            onToggle('grid')
          }
        />
      </section>

      <div className="layer-panel-note">
        <span aria-hidden="true">
          ◇
        </span>

        <p>
          Baseline sources include WorldPop,
          OpenStreetMap, AYNA-attributed linework
          and OpenData.az. Coverage and provenance
          limitations still apply.
        </p>
      </div>
    </aside>
  )
}

export default LayerPanel
