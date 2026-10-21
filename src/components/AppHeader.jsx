function AppHeader({
  theme,
  onToggleTheme,
  focusMode,
  onToggleFocusMode,
  onResetView,
  dataMode,
}) {
  const usingApi = dataMode === 'api'

  return (
    <header className="app-header">
      <div className="brand">
        <div
          className="brand-mark"
          aria-hidden="true"
        >
          B
        </div>

        <div className="brand-copy">
          <strong>Baku Mobility Lens</strong>
          <span>{dataMode === 'demo' ? 'Synthetic examples — not real findings' : 'Baku mobility accessibility study'}</span>
        </div>
      </div>

      <div className="header-context">
        <span>
          Urban accessibility & intervention planning
        </span>

        <span
          className={`data-mode-badge ${
            usingApi
              ? 'data-mode-api'
              : 'data-mode-prototype'
          }`}
          title={
            usingApi
              ? 'Frontend data loaded from the configured API'
              : dataMode === 'demo' ? 'Entirely made-up geometry and values for interface demonstration' : 'Frontend data loaded from local static files'
          }
        >
          <span
            className="data-mode-dot"
            aria-hidden="true"
          />

          {usingApi
            ? 'API data'
            : dataMode === 'demo' ? 'Synthetic demo' : 'Static data'}
        </span>
      </div>

      <div className="header-actions">
        <button
          type="button"
          className="overview-view-button"
          onClick={onResetView}
        >
          <span aria-hidden="true">
            ◎
          </span>

          Baku overview
        </button>

        <button
          type="button"
          className={`focus-mode-toggle ${
            focusMode ? 'active' : ''
          }`}
          onClick={onToggleFocusMode}
        >
          <span aria-hidden="true">
            {focusMode ? '↙' : '⌗'}
          </span>

          {focusMode
            ? 'Restore tools'
            : 'Focus map'}
        </button>

        <button
          type="button"
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={`Switch to ${
            theme === 'light'
              ? 'dark'
              : 'light'
          } mode`}
        >
          <span
            className="theme-toggle-icon"
            aria-hidden="true"
          >
            {theme === 'light'
              ? '◐'
              : '☀'}
          </span>

          <span>
            {theme === 'light'
              ? 'Dark'
              : 'Light'}
          </span>
        </button>
      </div>
    </header>
  )
}

export default AppHeader
