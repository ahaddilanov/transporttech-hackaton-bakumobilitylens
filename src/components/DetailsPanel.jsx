import './DetailsPanel.css'

function showValue(value, suffix = '') {
  if (value === null || value === undefined) {
    return 'Unavailable'
  }

  if (typeof value === 'number') {
    return `${value.toLocaleString()}${suffix}`
  }

  return `${value}${suffix}`
}

function getPriorityLabel(score) {
  if (score === null || score === undefined) {
    return 'Unavailable'
  }

  if (score >= 75) {
    return 'Very high need'
  }

  if (score >= 50) {
    return 'High need'
  }

  if (score >= 25) {
    return 'Moderate need'
  }

  return 'Low need'
}

function getPriorityClass(score) {
  if (score === null || score === undefined) {
    return 'priority-unavailable'
  }

  if (score >= 75) {
    return 'priority-very-high'
  }

  if (score >= 50) {
    return 'priority-high'
  }

  if (score >= 25) {
    return 'priority-moderate'
  }

  return 'priority-low'
}

function DetailRow({ label, value }) {
  return (
    <div className="feature-row">
      <span>{label}</span>

      <strong className="feature-value">
        {value}
      </strong>
    </div>
  )
}

function PriorityMeter({
  label,
  score,
}) {
  const hasScore =
    score !== null &&
    score !== undefined

  const safeScore = hasScore
    ? Math.max(
        0,
        Math.min(100, score)
      )
    : 0

  return (
    <div className="priority-meter">
      <div className="priority-meter-heading">
        <span>{label}</span>

        <strong>
          {hasScore
            ? `${score}/100`
            : 'Unavailable'}
        </strong>
      </div>

      <div className="priority-meter-track">
        <span
          className={`priority-meter-fill ${getPriorityClass(
            score
          )}`}
          style={{
            width: `${safeScore}%`,
          }}
        />
      </div>

      <span className="priority-meter-label">
        {getPriorityLabel(score)}
      </span>
    </div>
  )
}

function ReasonList({ reasons }) {
  if (
    !Array.isArray(reasons) ||
    reasons.length === 0
  ) {
    return (
      <p className="feature-panel-empty">
        Unavailable
      </p>
    )
  }

  return (
    <ul className="feature-reasons">
      {reasons.map(
        (reason, index) => (
          <li
            key={`${reason}-${index}`}
          >
            <span
              className="reason-marker"
              aria-hidden="true"
            >
              {index + 1}
            </span>

            <span>
              {reason}
            </span>
          </li>
        )
      )}
    </ul>
  )
}

function FeatureTypeBadge({ type }) {
  const proposed =
    type ===
      'Bus recommendation' ||
    type ===
      'Bike recommendation'

  const analysis =
    type === 'Grid cell'

  let label =
    'Existing infrastructure'

  if (proposed) {
    label =
      'Proposed improvement'
  }

  if (analysis) {
    label =
      'Analysis'
  }

  return (
    <span
      className={`feature-type-badge ${
        proposed
          ? 'feature-type-proposed'
          : analysis
            ? 'feature-type-analysis'
            : 'feature-type-existing'
      }`}
    >
      {label}
    </span>
  )
}

function DetailsPanel({
  selectedFeature,
  collapsed,
  onCollapse,
  onOpen,
}) {
  if (collapsed) {
    return (
      <button
        type="button"
        className="inspector-collapsed"
        onClick={onOpen}
        aria-label="Open map inspector"
      >
        <span className="inspector-collapsed-icon">
          ◇
        </span>

        <span className="inspector-collapsed-copy">
          <strong>
            Inspector
          </strong>

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

            <h2>
              Feature details
            </h2>
          </div>

          <button
            type="button"
            className="feature-panel-close"
            onClick={onCollapse}
            aria-label="Hide map inspector"
          >
            ×
          </button>
        </div>

        <div className="inspector-empty-state">
          <span
            className="inspector-empty-icon"
            aria-hidden="true"
          >
            ◇
          </span>

          <strong>
            Nothing selected
          </strong>

          <p>
            Select a grid cell,
            transport feature or
            recommendation to inspect
            its information.
          </p>
        </div>
      </aside>
    )
  }

  const {
    type,
    properties,
  } = selectedFeature

  const hasName = [
    'Bus stop',
    'Bus route',
    'Metro station',
    'Cycleway',
  ].includes(type)

  const title = hasName
    ? properties.name ??
      'Unnamed feature'
    : properties.id

  return (
    <aside className="feature-panel">
      <div className="feature-panel-header">
        <div className="feature-panel-heading">
          <p className="feature-panel-eyebrow">
            Map inspector
          </p>

          <FeatureTypeBadge
            type={type}
          />

          <h2>{title}</h2>

          <p className="feature-panel-type">
            {type}
          </p>
        </div>

        <button
          type="button"
          className="feature-panel-close"
          onClick={onCollapse}
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
          label="ID"
          value={properties.id}
        />

        {hasName && (
          <DetailRow
            label="Name"
            value={
              properties.name ??
              'Unavailable'
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

          <p className="feature-context-note">
            Daily validations are
            route-level context, not
            stop-level passenger demand.
          </p>
        </section>
      )}

      {type ===
        'Metro station' && (
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
              Accessibility context
            </p>

            <div className="inspector-stat-grid">
              <div className="inspector-stat">
                <span>
                  Population
                </span>

                <strong>
                  {showValue(
                    properties.population
                  )}
                </strong>
              </div>

              <div className="inspector-stat">
                <span>
                  Bus stops within
                  500 m
                </span>

                <strong>
                  {showValue(
                    properties.bus_stops_500m
                  )}
                </strong>
              </div>
            </div>

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
              Intervention need
            </p>

            <PriorityMeter
              label="Mobility gap"
              score={
                properties.mobility_gap
              }
            />

            <PriorityMeter
              label="Bus priority"
              score={
                properties.bus_priority
              }
            />

            <PriorityMeter
              label="Bike priority"
              score={
                properties.bike_priority
              }
            />

            <p className="feature-context-note">
              Higher scores indicate
              greater intervention need.
            </p>
          </section>
        </>
      )}

      {type ===
        'Bus recommendation' && (
        <>
          <section className="feature-section">
            <p className="feature-section-title">
              Intervention priority
            </p>

            <PriorityMeter
              label="Bus improvement"
              score={
                properties.priority
              }
            />
          </section>

          <section className="feature-section">
            <p className="feature-section-title">
              Expected impact
            </p>

            <div className="inspector-stat-grid">
              <div className="inspector-stat">
                <span>
                  Population
                  affected
                </span>

                <strong>
                  {showValue(
                    properties.population_affected
                  )}
                </strong>
              </div>

              <div className="inspector-stat inspector-stat-positive">
                <span>
                  Access
                  improvement
                </span>

                <strong>
                  {showValue(
                    properties.access_improvement_m,
                    ' m'
                  )}
                </strong>
              </div>
            </div>

            <div className="access-comparison">
              <div>
                <span>
                  Current access
                </span>

                <strong>
                  {showValue(
                    properties.current_access_m,
                    ' m'
                  )}
                </strong>
              </div>

              <span
                className="access-comparison-arrow"
                aria-hidden="true"
              >
                →
              </span>

              <div>
                <span>
                  New access
                </span>

                <strong>
                  {showValue(
                    properties.new_access_m,
                    ' m'
                  )}
                </strong>
              </div>
            </div>
          </section>

          <section className="feature-section">
            <p className="feature-section-title">
              Why proposed
            </p>

            <ReasonList
              reasons={
                properties.reason
              }
            />
          </section>
        </>
      )}

      {type ===
        'Bike recommendation' && (
        <>
          <section className="feature-section">
            <p className="feature-section-title">
              Candidate corridor
            </p>

            <div className="engineering-status">
              <span
                className="engineering-status-icon"
                aria-hidden="true"
              >
                ◇
              </span>

              <div>
                <strong>
                  Further engineering
                  assessment
                </strong>

                <span>
                  Candidate corridor,
                  not a construction-ready
                  plan.
                </span>
              </div>
            </div>

            <PriorityMeter
              label="Corridor priority"
              score={
                properties.priority
              }
            />
          </section>

          <section className="feature-section">
            <p className="feature-section-title">
              Corridor context
            </p>

            <div className="inspector-stat-grid">
              <div className="inspector-stat">
                <span>
                  Length
                </span>

                <strong>
                  {showValue(
                    properties.length_m,
                    ' m'
                  )}
                </strong>
              </div>

              <div className="inspector-stat">
                <span>
                  Population
                  coverage gain
                </span>

                <strong>
                  {showValue(
                    properties.population_coverage_gain
                  )}
                </strong>
              </div>
            </div>

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
              reasons={
                properties.reason
              }
            />
          </section>
        </>
      )}
    </aside>
  )
}

export default DetailsPanel