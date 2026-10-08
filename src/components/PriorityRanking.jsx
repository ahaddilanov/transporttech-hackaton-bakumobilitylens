import { useMemo, useState } from 'react'
import './PriorityRanking.css'

function getPriorityLabel(priority) {
  if (priority >= 75) {
    return 'Very high priority'
  }

  if (priority >= 50) {
    return 'High priority'
  }

  if (priority >= 25) {
    return 'Moderate priority'
  }

  return 'Low priority'
}

function PriorityRanking({
  busRecommendations,
  bikeRecommendations,
  selectedFeature,
  onSelect,
}) {
  const [activeType, setActiveType] = useState('bus')
  const [showAll, setShowAll] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  const recommendations = useMemo(() => {
    const source =
      activeType === 'bus'
        ? busRecommendations
        : bikeRecommendations

    if (!source?.features) {
      return []
    }

    return [...source.features].sort(
      (a, b) =>
        (b.properties.priority ?? 0) -
        (a.properties.priority ?? 0)
    )
  }, [activeType, busRecommendations, bikeRecommendations])

  const visibleRecommendations = showAll
    ? recommendations
    : recommendations.slice(0, 5)

  const featureType =
    activeType === 'bus'
      ? 'Bus recommendation'
      : 'Bike recommendation'

  function handleTypeChange(type) {
    setActiveType(type)
    setShowAll(false)
  }

  function handleSelect(feature) {
    onSelect({
      type: featureType,
      properties: feature.properties,
      feature,
      focusMap: true,
    })
  }

  function isSelected(feature) {
    return (
      selectedFeature?.type === featureType &&
      selectedFeature?.properties?.id ===
        feature.properties.id
    )
  }

  if (collapsed) {
    return (
      <button
        type="button"
        className="ranking-collapsed"
        onClick={() => setCollapsed(false)}
        aria-label="Open intervention priorities"
      >
        <span className="ranking-collapsed-rank">
          #1
        </span>

        <span className="ranking-collapsed-copy">
          <strong>Priorities</strong>
          <span>Decision support</span>
        </span>

        <span
          className="ranking-collapse-arrow"
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

          <h2>Intervention priorities</h2>

          <p className="ranking-subtitle">
            Ranked by backend intervention priority
          </p>
        </div>

        <button
          type="button"
          className="ranking-collapse-button"
          onClick={() => setCollapsed(true)}
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
            activeType === 'bus' ? 'active' : ''
          }
          onClick={() => handleTypeChange('bus')}
        >
          Bus
        </button>

        <button
          type="button"
          className={
            activeType === 'bike' ? 'active' : ''
          }
          onClick={() => handleTypeChange('bike')}
        >
          Cycling
        </button>
      </div>

      <div className="ranking-list">
        {visibleRecommendations.length > 0 ? (
          visibleRecommendations.map(
            (feature, index) => {
              const { id, priority } =
                feature.properties

              const title =
                activeType === 'bus'
                  ? 'Candidate Bus Improvement'
                  : 'Candidate Bicycle Corridor'

              return (
                <button
                  type="button"
                  className={`ranking-card ${
                    isSelected(feature)
                      ? 'selected'
                      : ''
                  }`}
                  key={id}
                  onClick={() =>
                    handleSelect(feature)
                  }
                >
                  <div className="ranking-position">
                    <span>#</span>
                    {index + 1}
                  </div>

                  <div className="ranking-card-content">
                    <span className="ranking-card-type">
                      {title}
                    </span>

                    <strong>{id}</strong>

                    <span className="ranking-priority-label">
                      {getPriorityLabel(priority)}
                    </span>

                    <div className="ranking-progress">
                      <span
                        style={{
                          width: `${priority}%`,
                        }}
                      />
                    </div>
                  </div>

                  <div className="ranking-score">
                    <strong>{priority}</strong>
                    <span>/100</span>
                  </div>
                </button>
              )
            }
          )
        ) : (
          <p className="ranking-empty">
            No recommendations available.
          </p>
        )}
      </div>

      <div className="ranking-footer">
        <span>
          {showAll
            ? `${recommendations.length} shown`
            : `Top ${Math.min(
                5,
                recommendations.length
              )} shown`}
        </span>

        {recommendations.length > 5 && (
          <button
            type="button"
            onClick={() =>
              setShowAll(
                (currentValue) => !currentValue
              )
            }
          >
            {showAll ? 'Show top 5' : 'View all'}
          </button>
        )}
      </div>
    </aside>
  )
}

export default PriorityRanking