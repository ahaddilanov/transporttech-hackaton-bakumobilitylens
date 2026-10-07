import { useEffect, useState } from 'react'
import L from 'leaflet'
import {
  GeoJSON,
  LayersControl,
  MapContainer,
  TileLayer,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

import { loadGeoJson } from './data/loadGeoJson'

function App() {
  const [busStops, setBusStops] = useState(null)
  const [busRoutes, setBusRoutes] = useState(null)
  const [metroStations, setMetroStations] = useState(null)
  const [cycleways, setCycleways] = useState(null)
  const [selectedFeature, setSelectedFeature] = useState(null)

  useEffect(() => {
    loadGeoJson('/data/bus_stops.geojson')
      .then((data) => {
        setBusStops(data)
      })
      .catch((error) => {
        console.error(error)
      })

    loadGeoJson('/data/bus_routes.geojson')
      .then((data) => {
        setBusRoutes(data)
      })
      .catch((error) => {
        console.error(error)
      })

    loadGeoJson('/data/metro_stations.geojson')
      .then((data) => {
        setMetroStations(data)
      })
      .catch((error) => {
        console.error(error)
      })

    loadGeoJson('/data/cycleways.geojson')
      .then((data) => {
        setCycleways(data)
      })
      .catch((error) => {
        console.error(error)
      })
  }, [])

  return (
    <div className="app">
      <MapContainer
        center={[40.4093, 49.8671]}
        zoom={12}
        className="map"
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <LayersControl position="topleft">
          {busRoutes && (
            <LayersControl.Overlay checked name="Bus Routes">
              <GeoJSON
                data={busRoutes}
                style={{
                  color: '#2563eb',
                  weight: 4,
                  opacity: 0.8,
                }}
                onEachFeature={(feature, layer) => {
                  layer.on('click', () => {
                    setSelectedFeature({
                      type: 'Bus route',
                      properties: feature.properties,
                    })
                  })
                }}
              />
            </LayersControl.Overlay>
          )}

          {cycleways && (
            <LayersControl.Overlay checked name="Cycleways">
              <GeoJSON
                data={cycleways}
                style={{
                  color: '#16a34a',
                  weight: 4,
                  opacity: 0.8,
                }}
                onEachFeature={(feature, layer) => {
                  layer.on('click', () => {
                    setSelectedFeature({
                      type: 'Cycleway',
                      properties: feature.properties,
                    })
                  })
                }}
              />
            </LayersControl.Overlay>
          )}

          {busStops && (
            <LayersControl.Overlay checked name="Bus Stops">
              <GeoJSON
                data={busStops}
                pointToLayer={(feature, latlng) =>
                  L.circleMarker(latlng, {
                    radius: 7,
                    weight: 2,
                    fillOpacity: 0.8,
                  })
                }
                onEachFeature={(feature, layer) => {
                  layer.on('click', () => {
                    setSelectedFeature({
                      type: 'Bus stop',
                      properties: feature.properties,
                    })
                  })
                }}
              />
            </LayersControl.Overlay>
          )}

          {metroStations && (
            <LayersControl.Overlay checked name="Metro Stations">
              <GeoJSON
                data={metroStations}
                pointToLayer={(feature, latlng) =>
                  L.circleMarker(latlng, {
                    radius: 9,
                    weight: 3,
                    fillOpacity: 0.9,
                  })
                }
                onEachFeature={(feature, layer) => {
                  layer.on('click', () => {
                    setSelectedFeature({
                      type: 'Metro station',
                      properties: feature.properties,
                    })
                  })
                }}
              />
            </LayersControl.Overlay>
          )}
        </LayersControl>
      </MapContainer>

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
                {selectedFeature.properties.avg_daily_entries ??
                  'Unavailable'}
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
    </div>
  )
}

export default App