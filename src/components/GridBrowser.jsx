import { useMemo, useState } from 'react'
import { showScore, showValue } from '../utils/presentation'

const PAGE_SIZE = 10

function GridResults({ grid, selectedMetric, onSelect }) {
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const matches = useMemo(() => {
    const search = query.trim().toLowerCase()
    return (grid?.features ?? []).filter(feature => feature.properties.id.toLowerCase().includes(search))
  }, [grid, query])
  const start = page * PAGE_SIZE
  return (
    <div className="grid-browser-results">
      <label htmlFor="grid-cell-search">Find an analysis cell by ID</label>
      <input id="grid-cell-search" type="search" value={query}
        onChange={event => { setQuery(event.target.value); setPage(0) }} placeholder="Search cell ID" />
      <p aria-live="polite">{showValue(matches.length)} matching cells. Scores use the selected metric.</p>
      <ul>
        {matches.slice(start, start + PAGE_SIZE).map(feature => (
          <li key={feature.properties.id}>
            <button type="button" onClick={() => onSelect({ type: 'Grid cell', properties: feature.properties, feature, focusMap: true })}>
              <span>{feature.properties.id}</span><strong>{showScore(feature.properties[selectedMetric])}</strong>
            </button>
          </li>
        ))}
      </ul>
      <div className="grid-browser-pages">
        <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
        <span>{matches.length ? `${start + 1}–${Math.min(start + PAGE_SIZE, matches.length)}` : 'No results'}</span>
        <button type="button" disabled={start + PAGE_SIZE >= matches.length} onClick={() => setPage(page + 1)}>Next</button>
      </div>
    </div>
  )
}

export default function GridBrowser(props) {
  const [open, setOpen] = useState(false)
  return (
    <section className="grid-browser">
      <button type="button" aria-expanded={open} aria-controls="grid-browser-content" onClick={() => setOpen(!open)}>
        {open ? 'Close cell browser' : 'Browse analysis cells (keyboard)'}
      </button>
      <div id="grid-browser-content">{open && <GridResults {...props} />}</div>
    </section>
  )
}
