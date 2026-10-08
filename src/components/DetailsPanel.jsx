function DetailsPanel({ selectedFeature }) {
  return (
    <aside className="details-panel">
      <h2>Feature details</h2>

      {selectedFeature ? (
        <>
          <p>
            <strong>Type:</strong> {selectedFeature.type}
          </p>

          <p>
            <strong>ID:</strong> {selectedFeature.properties.id}
          </p>

          {selectedFeature.type !== 'Grid cell' && (
            <p>
              <strong>Name:</strong>{' '}
              {selectedFeature.properties.name ?? 'Unavailable'}
            </p>
          )}

          {selectedFeature.type === 'Bus route' && (
            <>
              <p>
                <strong>Route ref:</strong>{' '}
                {selectedFeature.properties.route_ref ?? 'Unavailable'}
              </p>

              <p>
                <strong>Avg. daily validations:</strong>{' '}
                {selectedFeature.properties.avg_daily_validations ??
                  'Unavailable'}
              </p>
            </>
          )}

          {selectedFeature.type === 'Metro station' && (
            <p>
              <strong>Avg. daily entries:</strong>{' '}
              {selectedFeature.properties.avg_daily_entries ?? 'Unavailable'}
            </p>
          )}

          {selectedFeature.type === 'Cycleway' && (
            <p>
              <strong>Length:</strong>{' '}
              {selectedFeature.properties.length_m !== null
                ? `${selectedFeature.properties.length_m} m`
                : 'Unavailable'}
            </p>
          )}

          {selectedFeature.type === 'Grid cell' && (
            <>
              <p>
                <strong>Population:</strong>{' '}
                {selectedFeature.properties.population ?? 'Unavailable'}
              </p>

              <p>
                <strong>Nearest bus stop:</strong>{' '}
                {selectedFeature.properties.nearest_bus_stop_m !== null
                  ? `${selectedFeature.properties.nearest_bus_stop_m} m`
                  : 'Unavailable'}
              </p>

              <p>
                <strong>Nearest metro:</strong>{' '}
                {selectedFeature.properties.nearest_metro_m !== null
                  ? `${selectedFeature.properties.nearest_metro_m} m`
                  : 'Unavailable'}
              </p>

              <p>
                <strong>Nearest cycleway:</strong>{' '}
                {selectedFeature.properties.nearest_cycleway_m !== null
                  ? `${selectedFeature.properties.nearest_cycleway_m} m`
                  : 'Unavailable'}
              </p>

              <p>
                <strong>Bus stops within 500 m:</strong>{' '}
                {selectedFeature.properties.bus_stops_500m ?? 'Unavailable'}
              </p>

              <p>
                <strong>Bus routes nearby:</strong>{' '}
                {selectedFeature.properties.bus_routes_nearby ?? 'Unavailable'}
              </p>

              <p>
                <strong>POIs nearby:</strong>{' '}
                {selectedFeature.properties.pois_nearby ?? 'Unavailable'}
              </p>

              <p>
                <strong>Bus priority:</strong>{' '}
                {selectedFeature.properties.bus_priority ?? 'Unavailable'}
              </p>

              <p>
                <strong>Bike priority:</strong>{' '}
                {selectedFeature.properties.bike_priority ?? 'Unavailable'}
              </p>

              <p>
                <strong>Mobility gap:</strong>{' '}
                {selectedFeature.properties.mobility_gap ?? 'Unavailable'}
              </p>
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