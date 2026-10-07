export async function loadGeoJson(path) {
  const response = await fetch(path)

  if (!response.ok) {
    throw new Error(`Failed to load GeoJSON: ${path}`)
  }

  return response.json()
}