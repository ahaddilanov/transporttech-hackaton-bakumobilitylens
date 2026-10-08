function showValue(value, suffix = '') {
  if (value === null || value === undefined) {
    return 'Unavailable'
  }

  return `${value}${suffix}`
}

function DetailsPanel({ selectedFeature }) {
  const properties = selectedFeature?.properties

  const hasName =
    selectedFeature &&
    ['Bus stop', 'Bus route', 'Metro station', 'Cycleway'].includes(
      selectedFeature.type
    )

  return (
    <aside className="details-panel">
      <h2>Feature details</h2>

      {selectedFeature ? (
        <>
          <p>
            <strong>Type:</strong> {selectedFeature.type}
          </p>

          <p>
            <strong>ID:</strong> {properties.id}
          </p>

          {hasName && (
            <p>
              <strong>Name:</strong> {properties.name ?? 'Unavailable'}
            </p>
          )}

          {selectedFeature.type === 'Bus route' && (
            <>
              <p>
                <strong>Route ref:</strong>{' '}
                {properties.route_ref ?? 'Unavailable'}
              </p>

              <p>
                <strong>Avg. daily validations:</strong>{' '}
                {properties.avg_daily_validations ?? 'Unavailable'}
              </p>
            </>
          )}

          {selectedFeature.type === 'Metro station' && (
            <p>
              <strong>Avg. daily entries:</strong>{' '}
              {properties.avg_daily_entries ?? 'Unavailable'}
            </p>
          )}

          {selectedFeature.type === 'Cycleway' && (
            <p>
              <strong>Length:</strong>{' '}
              {showValue(properties.length_m, ' m')}
            </p>
          )}

          {selectedFeature.type === 'Grid cell' && (
            <>
              <p>
                <strong>Population:</strong>{' '}
                {showValue(properties.population)}
              </p>

              <p>
                <strong>Nearest bus stop:</strong>{' '}
                {showValue(properties.nearest_bus_stop_m, ' m')}
              </p>

              <p>
                <strong>Nearest metro:</strong>{' '}
                {showValue(properties.nearest_metro_m, ' m')}
              </p>

              <p>
                <strong>Nearest cycleway:</strong>{' '}
                {showValue(properties.nearest_cycleway_m, ' m')}
              </p>

              <p>
                <strong>Bus stops within 500 m:</strong>{' '}
                {showValue(properties.bus_stops_500m)}
              </p>

              <p>
                <strong>Bus routes nearby:</strong>{' '}
                {showValue(properties.bus_routes_nearby)}
              </p>

              <p>
                <strong>POIs nearby:</strong>{' '}
                {showValue(properties.pois_nearby)}
              </p>

              <p>
                <strong>Bus priority:</strong>{' '}
                {showValue(properties.bus_priority)}
              </p>

              <p>
                <strong>Bike priority:</strong>{' '}
                {showValue(properties.bike_priority)}
              </p>

              <p>
                <strong>Mobility gap:</strong>{' '}
                {showValue(properties.mobility_gap)}
              </p>
            </>
          )}

          {selectedFeature.type === 'Bus recommendation' && (
            <>
              <p>
                <strong>Priority:</strong>{' '}
                {showValue(properties.priority)}
              </p>

              <p>
                <strong>Population affected:</strong>{' '}
                {showValue(properties.population_affected)}
              </p>

              <p>
                <strong>Current access:</strong>{' '}
                {showValue(properties.current_access_m, ' m')}
              </p>

              <p>
                <strong>New access:</strong>{' '}
                {showValue(properties.new_access_m, ' m')}
              </p>

              <p>
                <strong>Access improvement:</strong>{' '}
                {showValue(properties.access_improvement_m, ' m')}
              </p>

              <strong>Reason:</strong>

              {Array.isArray(properties.reason) &&
              properties.reason.length > 0 ? (
                <ul>
                  {properties.reason.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : (
                <p>Unavailable</p>
              )}
            </>
          )}

          {selectedFeature.type === 'Bike recommendation' && (
            <>
              <p>
                <strong>Status:</strong>{' '}
                Candidate corridor for further engineering assessment
              </p>

              <p>
                <strong>Priority:</strong>{' '}
                {showValue(properties.priority)}
              </p>

              <p>
                <strong>Length:</strong>{' '}
                {showValue(properties.length_m, ' m')}
              </p>

              <p>
                <strong>Population coverage gain:</strong>{' '}
                {showValue(properties.population_coverage_gain)}
              </p>

              <p>
                <strong>Start:</strong>{' '}
                {properties.start_name ?? 'Unavailable'}
              </p>

              <p>
                <strong>End:</strong>{' '}
                {properties.end_name ?? 'Unavailable'}
              </p>

              <strong>Reason:</strong>

              {Array.isArray(properties.reason) &&
              properties.reason.length > 0 ? (
                <ul>
                  {properties.reason.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : (
                <p>Unavailable</p>
              )}
            </>
          )}
        </>
      ) : (
        <p>Click a map feature to view its details.</p>
      )}
    </aside>
  )
}

export default DetailsPanel