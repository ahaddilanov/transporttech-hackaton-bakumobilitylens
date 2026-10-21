import { useState } from 'react'

export default function FeatureIdentifier({ id }) {
  const [message, setMessage] = useState('')
  async function copyId() {
    try {
      await navigator.clipboard.writeText(id)
      setMessage('Copied')
    } catch {
      setMessage('Copy unavailable. Select the full ID below to copy it manually.')
    }
  }
  return (
    <details className="feature-identifier">
      <summary>Full identifier</summary>
      <code>{id}</code>
      <button type="button" onClick={copyId}>Copy ID</button>
      <span role="status">{message}</span>
    </details>
  )
}
