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

          <p>
            <strong>Name:</strong>{' '}
            {selectedFeature.properties.name ?? 'Unavailable'}
          </p>

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
        </>
      ) : (
        <p>Click a map feature to view its details.</p>
      )}
    </aside>
  )
}

export default DetailsPanel