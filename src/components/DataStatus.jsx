import './DataStatus.css'

function DataStatus({ loading, errors }) {
  const hasErrors =
    Array.isArray(errors) && errors.length > 0

  if (!loading && !hasErrors) {
    return null
  }

  return (
    <div
      className="data-status-stack"
      aria-live="polite"
      aria-atomic="true"
    >
      {loading && (
        <div className="data-status-card data-status-loading">
          <span
            className="data-status-spinner"
            aria-hidden="true"
          />

          <div className="data-status-copy">
            <strong>
              Loading mobility data
            </strong>

            <span>
              Preparing map layers and analysis.
            </span>
          </div>
        </div>
      )}

      {!loading && hasErrors && (
        <div className="data-status-card data-status-error">
          <div
            className="data-status-error-icon"
            aria-hidden="true"
          >
            !
          </div>

          <div className="data-status-error-content">
            <div className="data-status-copy">
              <strong>
                Some data could not be loaded
              </strong>

              <span>
                Available datasets are still shown on
                the map.
              </span>
            </div>

            <div className="data-status-error-list">
              {errors.map((error, index) => (
                <div
                  className="data-status-error-item"
                  key={`${error}-${index}`}
                >
                  {error}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DataStatus