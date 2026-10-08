import {
  useMemo,
  useState,
} from 'react'
import './PriorityRanking.css'

function showValue(
  value,
  suffix = ''
) {
  if (
    value === null ||
    value === undefined
  ) {
    return 'Unavailable'
  }

  if (
    typeof value === 'number'
  ) {
    return `${value.toLocaleString()}${suffix}`
  }

  return `${value}${suffix}`
}

function getPriorityLabel(score) {
  if (
    score === null ||
    score === undefined
  ) {
    return 'Unavailable'
  }

  if (score >= 75) {
    return 'Very high'
  }

  if (score >= 50) {
    return 'High'
  }

  if (score >= 25) {
    return 'Moderate'
  }

  return 'Low'
}

function getPriorityClass(score) {
  if (
    score === null ||
    score === undefined
  ) {
    return 'ranking-score-unavailable'
  }

  if (score >= 75) {
    return 'ranking-score-very-high'
  }

  if (score >= 50) {
    return 'ranking-score-high'
  }

  if (score >= 25) {
    return 'ranking-score-moderate'
  }

  return 'ranking-score-low'
}

function PriorityRanking({
  busRecommendations,
  bikeRecommendations,
  selectedFeature,
  onSelect,
}) {
  const [
    activeType,
    setActiveType,
  ] = useState('bus')

  const [showAll, setShowAll] =
    useState(false)

  /*
    Start collapsed so the initial map
    remains visually clean.
  */
  const [
    collapsed,
    setCollapsed,
  ] = useState(true)

  const busFeatures =
    busRecommendations?.features ??
    []

  const bikeFeatures =
    bikeRecommendations?.features ??
    []

  const recommendations =
    activeType === 'bus'
      ? busFeatures
      : bikeFeatures

  const sortedRecommendations =
    useMemo(() => {
      return [
        ...recommendations,
      ].sort((a, b) => {
        const aPriority =
          a.properties?.priority ??
          -1

        const bPriority =
          b.properties?.priority ??
          -1

        return (
          bPriority -
          aPriority
        )
      })
    }, [recommendations])

  const visibleRecommendations =
    showAll
      ? sortedRecommendations
      : sortedRecommendations.slice(
          0,
          5
        )

  const featureType =
    activeType === 'bus'
      ? 'Bus recommendation'
      : 'Bike recommendation'

  function handleTypeChange(
    type
  ) {
    setActiveType(type)
    setShowAll(false)
  }

  function handleSelect(
    feature
  ) {
    onSelect({
      type: featureType,
      properties:
        feature.properties,
      feature,
      focusMap: true,
    })
  }

  function isSelected(
    feature
  ) {
    return (
      selectedFeature?.type ===
        featureType &&
      selectedFeature
        ?.properties?.id ===
        feature.properties?.id
    )
  }

  if (collapsed) {
    return (
      <button
        type="button"
        className="ranking-collapsed"
        onClick={() =>
          setCollapsed(false)
        }
        aria-label="Open intervention priorities"
      >
        <span className="ranking-collapsed-rank">
          #1
        </span>

        <span className="ranking-collapsed-copy">
          <strong>
            Priorities
          </strong>

          <span>
            Decision support
          </span>
        </span>

        <span
          className="ranking-collapsed-arrow"
          aria-hidden="true"
        >
          ›
        </span>
      </button>
    )
  }

  return (
    <aside className="priority-ranking">
      <div className="ranking-header">
        <div>
          <p className="ranking-eyebrow">
            Decision support
          </p>

          <h2>
            Intervention priorities
          </h2>

          <p className="ranking-description">
            Ranked by backend
            intervention priority.
          </p>
        </div>

        <button
          type="button"
          className="ranking-collapse-button"
          onClick={() =>
            setCollapsed(true)
          }
          aria-label="Collapse intervention priorities"
        >
          ‹
        </button>
      </div>

      <div
        className="ranking-tabs"
        role="tablist"
        aria-label="Recommendation type"
      >
        <button
          type="button"
          className={
            activeType === 'bus'
              ? 'active'
              : ''
          }
          onClick={() =>
            handleTypeChange(
              'bus'
            )
          }
        >
          Bus
          <span>
            {busFeatures.length}
          </span>
        </button>

        <button
          type="button"
          className={
            activeType === 'bike'
              ? 'active'
              : ''
          }
          onClick={() =>
            handleTypeChange(
              'bike'
            )
          }
        >
          Cycling
          <span>
            {bikeFeatures.length}
          </span>
        </button>
      </div>

      {sortedRecommendations.length ===
      0 ? (
        <div className="ranking-empty">
          <span
            className="ranking-empty-icon"
            aria-hidden="true"
          >
            ◇
          </span>

          <strong>
            No recommendations
            available
          </strong>

          <p>
            This layer currently
            contains no candidate
            interventions.
          </p>
        </div>
      ) : (
        <>
          <div className="ranking-list">
            {visibleRecommendations.map(
              (
                feature,
                index
              ) => {
                const properties =
                  feature.properties

                const selected =
                  isSelected(
                    feature
                  )

                const priority =
                  properties.priority

                return (
                  <button
                    type="button"
                    className={`ranking-card ${
                      selected
                        ? 'selected'
                        : ''
                    }`}
                    key={
                      properties.id
                    }
                    onClick={() =>
                      handleSelect(
                        feature
                      )
                    }
                    aria-pressed={
                      selected
                    }
                  >
                    <div className="ranking-card-top">
                      <span className="ranking-position">
                        #
                        {index +
                          1}
                      </span>

                      <span
                        className={`ranking-need ${getPriorityClass(
                          priority
                        )}`}
                      >
                        {getPriorityLabel(
                          priority
                        )}
                      </span>
                    </div>

                    <div className="ranking-card-heading">
                      <div>
                        <strong>
                          {activeType ===
                          'bus'
                            ? 'Candidate Bus Improvement'
                            : 'Candidate Bicycle Corridor'}
                        </strong>

                        <span>
                          {
                            properties.id
                          }
                        </span>
                      </div>

                      <div className="ranking-score">
                        <strong>
                          {priority ??
                            '—'}
                        </strong>

                        <span>
                          /100
                        </span>
                      </div>
                    </div>

                    <div className="ranking-progress">
                      <span
                        className={getPriorityClass(
                          priority
                        )}
                        style={{
                          width: `${
                            priority ??
                            0
                          }%`,
                        }}
                      />
                    </div>

                    {activeType ===
                    'bus' ? (
                      <div className="ranking-metrics">
                        <div>
                          <span>
                            Population
                          </span>

                          <strong>
                            {showValue(
                              properties.population_affected
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>
                            Access gain
                          </span>

                          <strong>
                            {showValue(
                              properties.access_improvement_m,
                              ' m'
                            )}
                          </strong>
                        </div>
                      </div>
                    ) : (
                      <div className="ranking-metrics">
                        <div>
                          <span>
                            Coverage gain
                          </span>

                          <strong>
                            {showValue(
                              properties.population_coverage_gain
                            )}
                          </strong>
                        </div>

                        <div>
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
                      </div>
                    )}

                    <div className="ranking-card-action">
                      <span>
                        View on map
                      </span>

                      <span
                        aria-hidden="true"
                      >
                        →
                      </span>
                    </div>
                  </button>
                )
              }
            )}
          </div>

          <div className="ranking-footer">
            <span>
              Showing{' '}
              {
                visibleRecommendations.length
              }{' '}
              of{' '}
              {
                sortedRecommendations.length
              }
            </span>

            {sortedRecommendations.length >
              5 && (
              <button
                type="button"
                onClick={() =>
                  setShowAll(
                    (
                      current
                    ) =>
                      !current
                  )
                }
              >
                {showAll
                  ? 'Show top 5'
                  : 'View all'}
              </button>
            )}
          </div>

          {activeType ===
            'bike' && (
            <p className="ranking-engineering-note">
              Candidate corridors
              require further
              engineering assessment.
            </p>
          )}
        </>
      )}
    </aside>
  )
}

export default PriorityRanking