function AppHeader({
  theme,
  onToggleTheme,
  focusMode,
  onToggleFocusMode,
}) {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          T
        </div>

        <div className="brand-copy">
          <strong>TransportTech</strong>
          <span>Baku mobility planning</span>
        </div>
      </div>

      <div className="header-context">
        Urban accessibility & intervention planning
      </div>

      <div className="header-actions">
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

          {focusMode ? 'Restore tools' : 'Focus map'}
        </button>

        <button
          type="button"
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={`Switch to ${
            theme === 'light' ? 'dark' : 'light'
          } mode`}
        >
          <span
            className="theme-toggle-icon"
            aria-hidden="true"
          >
            {theme === 'light' ? '◐' : '☀'}
          </span>

          <span>
            {theme === 'light' ? 'Dark' : 'Light'}
          </span>
        </button>
      </div>
    </header>
  )
}

export default AppHeader