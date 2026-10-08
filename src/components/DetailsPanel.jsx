import { useState } from 'react'
import './DetailsPanel.css'

function showValue(value, suffix = '') {
  if (value === null || value === undefined) {
    return 'Unavailable'
  }

  return `${value}${suffix}`
}

function DetailRow({ label, value }) {
  return (
    <div className="feature-row">
      <span>{label}</span>
      <span className="feature-value">{value}</span>
    </div>
  )
}

function ReasonList({ reasons }) {
  if (!Array.isArray(reasons) || reasons.length === 0) {
    return (
      <p className="feature-panel-empty">
        Unavailable
      </p>
    )
  }

  return (
    <ul className="feature-reasons">
      {reasons.map((reason) => (
        <li key={reason}>{reason}</li>
      ))}
    </ul>
  )
}

function DetailsPanel({ selectedFeature }) {
  const [collapsed, setCollapsed] = useState(false)

  if (collapsed) {
    return (
      <button
        type="button"
        className="inspector-collapsed"
        onClick={() => setCollapsed(false)}
        aria-label="Open map inspector"
      >
        <span className="inspector-collapsed-icon">
          ◇
        </span>

        <span className="inspector-collapsed-copy">
          <strong>Inspector</strong>
          <span>
            {selectedFeature
              ? selectedFeature.type
              : 'Feature details'}
          </span>
        </span>

        <span
          className="inspector-collapsed-arrow"
          aria-hidden="true"
        >
          ‹
        </span>
      </button>
    )
  }

  if (!selectedFeature) {
    return (
      <aside className="feature-panel">
        <div className="feature-panel-header">
          <div>
            <p className="feature-panel-eyebrow">
              Map inspector
            </p>

            <h2>Feature details</h2>
          </div>

          <button
            type="button"
            className="feature-panel-close"
            onClick={() => setCollapsed(true)}
            aria-label="Hide map inspector"
          >
            ×
          </button>
        </div>

        <p className="feature-panel-empty">
          Select a map feature to inspect its information.
        </p>
      </aside>
    )
  }

  const { type, properties } = selectedFeature

  const hasName = [
    'Bus stop',
    'Bus route',
    'Metro station',
    'Cycleway',
  ].includes(type)

  return (
    <aside className="feature-panel">
      <div className="feature-panel-header">
        <div>
          <p className="feature-panel-eyebrow">
            {type}
          </p>

          <h2>
            {hasName
              ? properties.name ?? 'Unnamed feature'
              : properties.id}
          </h2>
        </div>

        <button
          type="button"
          className="feature-panel-close"
          onClick={() => setCollapsed(true)}
          aria-label="Hide map inspector"
        >
          ×
        </button>
      </div>

      <section className="feature-section">
        <p className="feature-section-title">
          Identity
        </p>

        <DetailRow
          label="Type"
          value={type}
        />

        <DetailRow
          label="ID"
          value={properties.id}
        />

        {hasName && (
          <DetailRow
            label="Name"
            value={
              properties.name ?? 'Unavailable'
            }
          />
        )}
      </section>

      {type === 'Bus route' && (
        <section className="feature-section">
          <p className="feature-section-title">
            Route context
          </p>

          <DetailRow
            label="Route reference"
            value={
              properties.route_ref ??
              'Unavailable'
            }
          />

          <DetailRow
            label="Avg. daily validations"
            value={showValue(
              properties.avg_daily_validations
            )}
          />
        </section>
      )}

      {type === 'Metro station' && (
        <section className="feature-section">
          <p className="feature-section-title">
            Station context
          </p>

          <DetailRow
            label="Avg. daily entries"
            value={showValue(
              properties.avg_daily_entries
            )}
          />
        </section>
      )}

      {type === 'Cycleway' && (
        <section className="feature-section">
          <p className="feature-section-title">
            Infrastructure
          </p>

          <DetailRow
            label="Length"
            value={showValue(
              properties.length_m,
              ' m'
            )}
          />
        </section>
      )}

      {type === 'Grid cell' && (
        <>
          <section className="feature-section">
            <p className="feature-section-title">
              Accessibility
            </p>

            <DetailRow
              label="Population"
              value={showValue(
                properties.population
              )}
            />

            <DetailRow
              label="Nearest bus stop"
              value={showValue(
                properties.nearest_bus_stop_m,
                ' m'
              )}
            />

            <DetailRow
              label="Nearest metro"
              value={showValue(
                properties.nearest_metro_m,
                ' m'
              )}
            />

            <DetailRow
              label="Nearest cycleway"
              value={showValue(
                properties.nearest_cycleway_m,
                ' m'
              )}
            />

            <DetailRow
              label="Bus stops within 500 m"
              value={showValue(
                properties.bus_stops_500m
              )}
            />

            <DetailRow
              label="Bus routes nearby"
              value={showValue(
                properties.bus_routes_nearby
              )}
            />

            <DetailRow
              label="POIs nearby"
              value={showValue(
                properties.pois_nearby
              )}
            />
          </section>

          <section className="feature-section">
            <p className="feature-section-title">
              Priority scores
            </p>

            <DetailRow
              label="Bus priority"
              value={showValue(
                properties.bus_priority
              )}
            />

            <DetailRow
              label="Bike priority"
              value={showValue(
                properties.bike_priority
              )}
            />

            <DetailRow
              label="Mobility gap"
              value={showValue(
                properties.mobility_gap
              )}
            />
          </section>
        </>
      )}

      {type === 'Bus recommendation' && (
        <>
          <section className="feature-section">
            <p className="feature-section-title">
              Expected impact
            </p>

            <DetailRow
              label="Priority"
              value={showValue(
                properties.priority
              )}
            />

            <DetailRow
              label="Population affected"
              value={showValue(
                properties.population_affected
              )}
            />

            <DetailRow
              label="Current access"
              value={showValue(
                properties.current_access_m,
                ' m'
              )}
            />

            <DetailRow
              label="New access"
              value={showValue(
                properties.new_access_m,
                ' m'
              )}
            />

            <DetailRow
              label="Access improvement"
              value={showValue(
                properties.access_improvement_m,
                ' m'
              )}
            />
          </section>

          <section className="feature-section">
            <p className="feature-section-title">
              Why proposed
            </p>

            <ReasonList
              reasons={properties.reason}
            />
          </section>
        </>
      )}

      {type === 'Bike recommendation' && (
        <>
          <section className="feature-section">
            <p className="feature-section-title">
              Candidate corridor
            </p>

            <DetailRow
              label="Status"
              value="Further engineering assessment"
            />

            <DetailRow
              label="Priority"
              value={showValue(
                properties.priority
              )}
            />

            <DetailRow
              label="Length"
              value={showValue(
                properties.length_m,
                ' m'
              )}
            />

            <DetailRow
              label="Coverage gain"
              value={showValue(
                properties.population_coverage_gain
              )}
            />

            <DetailRow
              label="Start"
              value={
                properties.start_name ??
                'Unavailable'
              }
            />

            <DetailRow
              label="End"
              value={
                properties.end_name ??
                'Unavailable'
              }
            />
          </section>

          <section className="feature-section">
            <p className="feature-section-title">
              Why proposed
            </p>

            <ReasonList
              reasons={properties.reason}
            />
          </section>
        </>
      )}
    </aside>
  )
}

export default DetailsPanel