function ScoreSelector({ selectedMetric, onChange }) {
  return (
    <div className="score-selector">
      <button
        type="button"
        className={selectedMetric === 'mobility_gap' ? 'active' : ''}
        onClick={() => onChange('mobility_gap')}
      >
        Mobility Gap
      </button>

      <button
        type="button"
        className={selectedMetric === 'bus_priority' ? 'active' : ''}
        onClick={() => onChange('bus_priority')}
      >
        Bus Priority
      </button>

      <button
        type="button"
        className={selectedMetric === 'bike_priority' ? 'active' : ''}
        onClick={() => onChange('bike_priority')}
      >
        Bike Priority
      </button>
    </div>
  )
}

export default ScoreSelector