import L from 'leaflet'

// Scoped to our immutable grid and Leaflet 1.9's Canvas lifecycle. Feature
// layers remain attached; only the renderer's working set is viewport-limited.
export default class ClickOnlyCanvas extends L.Canvas {
  constructor(options) {
    super(options)
    this._projectedAt = new WeakMap()
    this._visibleLayers = []
    this._visibleDirty = true
  }

  setBoundsIndex(index) {
    this._boundsIndex = index
    return this
  }

  _viewKey() {
    const origin = this._map.getPixelOrigin()
    return `${this._map.getZoom()}:${origin.x}:${origin.y}`
  }

  _refreshVisiblePaths() {
    if (!this._visibleDirty) return
    if (!this._drawFirst) {
      this._visibleLayers = []
      this._visibleOrder = null
      this._visibleDirty = false
      return
    }
    // Exceed Canvas's 10% clip padding slightly to cover strokes at its edges.
    const bounds = this._map.getBounds().pad(this.options.padding + 0.05)
    const candidates = this._boundsIndex.search([
      bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth(),
    ])
    this._visibleLayers = candidates.filter(layer => this._layers[L.stamp(layer)])
    // A separate draw list leaves Leaflet's full membership/order list intact.
    this._visibleOrder = this._visibleLayers.reduceRight((next, layer) => ({ layer, next }), null)
    this._visibleDirty = false
  }

  _withVisiblePaths(callback, ...args) {
    this._refreshVisiblePaths()
    const allPaths = this._drawFirst
    this._drawFirst = this._visibleOrder
    try { return callback.apply(this, args) } finally { this._drawFirst = allPaths }
  }

  _initContainer() {
    super._initContainer()
    L.DomEvent.off(this._container, 'mousemove', this._onMouseMove, this)
    L.DomEvent.off(this._container, 'mouseout', this._handleMouseOut, this)
  }

  _addPath(layer) {
    this._projectedAt.set(layer, this._viewKey())
    this._visibleDirty = true
    super._addPath(layer)
  }

  _removePath(layer) {
    this._visibleDirty = true
    super._removePath(layer)
  }

  _onClick(event) {
    if (!this._map) return
    if (event.type !== 'click') {
      // Preserve map double-click zoom without doing polygon hit tests.
      this._fireEvent(false, event)
      return
    }
    if (this._map._animatingZoom || this._map._draggableMoved(this._map)) return
    this._withVisiblePaths(L.Canvas.prototype._onClick, event)
  }

  _onZoomEnd() {
    // Defer projection to the immediately following moveend/updatePaths pass,
    // when both the target view and the renderer's clipping bounds are current.
    this._visibleDirty = true
  }

  _reset() {
    // Renderer._reset would reset every registered polygon after _update.
    // Our updatePaths already projects and clips the visible working set.
    this._update()
    this._updateTransform(this._center, this._zoom)
    if (this._postponeUpdatePaths) {
      this._postponeUpdatePaths = false
      this._updatePaths()
    }
  }

  _updatePaths() {
    if (this._postponeUpdatePaths) return
    L.Util.cancelAnimFrame(this._redrawRequest)
    this._redrawRequest = null
    this._redrawBounds = null
    this._visibleDirty = true
    this._refreshVisiblePaths()
    const view = this._viewKey()
    for (const layer of this._visibleLayers) {
      if (this._projectedAt.get(layer) !== view) {
        layer._project()
        this._projectedAt.set(layer, view)
      }
      layer._update()
    }
    this._redraw()
  }

  _draw() {
    this._withVisiblePaths(L.Canvas.prototype._draw)
  }
}
