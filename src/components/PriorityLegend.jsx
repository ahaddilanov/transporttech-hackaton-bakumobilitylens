function PriorityLegend({ selectedMetric }) {
  const titles = {
    mobility_gap: 'Mobility Gap',
    bus_priority: 'Bus Priority',
    bike_priority: 'Bike Priority',
  }

  return (
    <div className="priority-legend">
      <h3>{titles[selectedMetric]}</h3>

      <p className="legend-note">
        Higher score = greater need
      </p>

      <div className="legend-row">
        <span className="legend-color legend-low"></span>
        <span>0–24 Low</span>
      </div>

      <div className="legend-row">
        <span className="legend-color legend-moderate"></span>
        <span>25–49 Moderate</span>
      </div>

      <div className="legend-row">
        <span className="legend-color legend-high"></span>
        <span>50–74 High</span>
      </div>

      <div className="legend-row">
        <span className="legend-color legend-very-high"></span>
        <span>75–100 Very high</span>
      </div>

      <div className="legend-row">
        <span className="legend-color legend-unavailable"></span>
        <span>Unavailable</span>
      </div>
    </div>
  )
}

export default PriorityLegend