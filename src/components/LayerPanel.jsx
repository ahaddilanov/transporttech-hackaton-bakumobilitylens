import { useState } from 'react'
import './LayerPanel.css'

function LayerToggle({
  label,
  description,
  checked,
  onChange,
}) {
  return (
    <label className="layer-toggle">
      <div className="layer-toggle-copy">
        <strong>{label}</strong>
        <span>{description}</span>
      </div>

      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
      />

      <span className="layer-switch" aria-hidden="true">
        <span />
      </span>
    </label>
  )
}

function LayerPanel({ visibility, onToggle }) {
  const [collapsed, setCollapsed] = useState(true)

  if (collapsed) {
    return (
      <button
        type="button"
        className="layers-collapsed"
        onClick={() => setCollapsed(false)}
        aria-label="Open map layers"
      >
        <span className="layers-collapsed-icon">
          ≡
        </span>

        <span className="layers-collapsed-copy">
          <strong>Map layers</strong>
          <span>Infrastructure & analysis</span>
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
        </div>

        <button
          type="button"
          className="layer-panel-collapse"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse map layers"
        >
          ×
        </button>
      </div>

      <section className="layer-section">
        <p className="layer-section-title">
          Existing infrastructure
        </p>

        <LayerToggle
          label="Bus stops"
          description="Existing stop locations"
          checked={visibility.busStops}
          onChange={() => onToggle('busStops')}
        />

        <LayerToggle
          label="Bus routes"
          description="Existing route geometry"
          checked={visibility.busRoutes}
          onChange={() => onToggle('busRoutes')}
        />

        <LayerToggle
          label="Metro stations"
          description="Existing metro access"
          checked={visibility.metroStations}
          onChange={() =>
            onToggle('metroStations')
          }
        />

        <LayerToggle
          label="Cycleways"
          description="Existing cycling infrastructure"
          checked={visibility.cycleways}
          onChange={() => onToggle('cycleways')}
        />
      </section>

      <section className="layer-section">
        <p className="layer-section-title">
          Analysis
        </p>

        <LayerToggle
          label="Priority grid"
          description="Current selected analysis score"
          checked={visibility.grid}
          onChange={() => onToggle('grid')}
        />
      </section>

      <section className="layer-section">
        <p className="layer-section-title">
          Proposed improvements
        </p>

        <LayerToggle
          label="Candidate bus improvements"
          description="Public-transport interventions"
          checked={visibility.busRecommendations}
          onChange={() =>
            onToggle('busRecommendations')
          }
        />

        <LayerToggle
          label="Candidate bicycle corridors"
          description="Further engineering assessment"
          checked={visibility.bikeRecommendations}
          onChange={() =>
            onToggle('bikeRecommendations')
          }
        />
      </section>
    </aside>
  )
}

export default LayerPanel