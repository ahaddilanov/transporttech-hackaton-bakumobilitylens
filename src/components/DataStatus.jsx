function DataStatus({ loading, errors }) {
  if (loading) {
    return (
      <div className="data-status data-status-loading">
        Loading mobility data...
      </div>
    )
  }

  if (errors.length > 0) {
    return (
      <div className="data-status data-status-error">
        <strong>Some data could not be loaded.</strong>

        <ul>
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      </div>
    )
  }

  return null
}

export default DataStatus