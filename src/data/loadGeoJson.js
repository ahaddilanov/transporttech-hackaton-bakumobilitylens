export async function loadJson(path) {
  const response = await fetch(path)

  if (!response.ok) {
    throw new Error(
      `Failed to load ${path}: ${response.status} ${response.statusText}`
    )
  }

  return response.json()
}

export async function loadGeoJson(path) {
  return loadJson(path)
}