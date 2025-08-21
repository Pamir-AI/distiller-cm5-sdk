/**
 * State management for the E-ink Composer
 */

class State {
    constructor() {
        this.layers = [];
        this.selectedLayerId = null;
        this.canvas = {
            width: 250,
            height: 128
        };
        this.grid = {
            enabled: true,
            size: 10
        };
        this.snap = {
            enabled: true,
            threshold: 5
        };
        this.tool = 'select';
        this.history = [];
        this.historyIndex = -1;
        this.maxHistory = 50;
        this.listeners = {};
        this.isDragging = false;
        this.dragStart = null;
        this.hardwareInfo = null;
    }

    /**
     * Subscribe to state changes
     */
    subscribe(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
        
        // Return unsubscribe function
        return () => {
            const index = this.listeners[event].indexOf(callback);
            if (index > -1) {
                this.listeners[event].splice(index, 1);
            }
        };
    }

    /**
     * Emit an event
     */
    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => callback(data));
        }
    }

    /**
     * Add a layer
     */
    addLayer(layer) {
        this.layers.push(layer);
        this.saveHistory();
        this.emit('layersChanged', this.layers);
        return layer.id;
    }

    /**
     * Update a layer
     */
    updateLayer(layerId, updates) {
        const layer = this.layers.find(l => l.id === layerId);
        if (layer) {
            Object.assign(layer, updates);
            this.saveHistory();
            this.emit('layerUpdated', layer);
            this.emit('layersChanged', this.layers);
            return true;
        }
        return false;
    }

    /**
     * Remove a layer
     */
    removeLayer(layerId) {
        const index = this.layers.findIndex(l => l.id === layerId);
        if (index > -1) {
            this.layers.splice(index, 1);
            if (this.selectedLayerId === layerId) {
                this.selectedLayerId = null;
                this.emit('selectionChanged', null);
            }
            this.saveHistory();
            this.emit('layersChanged', this.layers);
            return true;
        }
        return false;
    }

    /**
     * Toggle layer visibility
     */
    toggleLayerVisibility(layerId) {
        const layer = this.layers.find(l => l.id === layerId);
        if (layer) {
            layer.visible = !layer.visible;
            this.emit('layerUpdated', layer);
            this.emit('layersChanged', this.layers);
            return true;
        }
        return false;
    }

    /**
     * Reorder layers
     */
    reorderLayer(layerId, newIndex) {
        const oldIndex = this.layers.findIndex(l => l.id === layerId);
        if (oldIndex > -1 && newIndex >= 0 && newIndex < this.layers.length) {
            const [layer] = this.layers.splice(oldIndex, 1);
            this.layers.splice(newIndex, 0, layer);
            this.saveHistory();
            this.emit('layersChanged', this.layers);
            return true;
        }
        return false;
    }

    /**
     * Select a layer
     */
    selectLayer(layerId) {
        this.selectedLayerId = layerId;
        const layer = this.layers.find(l => l.id === layerId);
        this.emit('selectionChanged', layer);
    }

    /**
     * Get selected layer
     */
    getSelectedLayer() {
        return this.layers.find(l => l.id === this.selectedLayerId);
    }

    /**
     * Get all layers
     */
    getLayers() {
        return this.layers;
    }

    /**
     * Get visible layers
     */
    getVisibleLayers() {
        return this.layers.filter(l => l.visible);
    }

    /**
     * Clear all layers
     */
    clearLayers() {
        this.layers = [];
        this.selectedLayerId = null;
        this.saveHistory();
        this.emit('layersChanged', this.layers);
        this.emit('selectionChanged', null);
    }

    /**
     * Set current tool
     */
    setTool(tool) {
        this.tool = tool;
        this.emit('toolChanged', tool);
    }

    /**
     * Set canvas dimensions
     */
    setCanvasSize(width, height) {
        this.canvas.width = width;
        this.canvas.height = height;
        this.emit('canvasSizeChanged', { width, height });
    }

    /**
     * Toggle grid
     */
    toggleGrid() {
        this.grid.enabled = !this.grid.enabled;
        this.emit('gridChanged', this.grid);
    }

    /**
     * Toggle snap
     */
    toggleSnap() {
        this.snap.enabled = !this.snap.enabled;
        this.emit('snapChanged', this.snap);
    }

    /**
     * Save current state to history
     */
    saveHistory() {
        // Remove any history after current index
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // Add current state
        this.history.push({
            layers: JSON.parse(JSON.stringify(this.layers)),
            selectedLayerId: this.selectedLayerId
        });
        
        // Limit history size
        if (this.history.length > this.maxHistory) {
            this.history.shift();
        } else {
            this.historyIndex++;
        }
        
        this.emit('historyChanged', {
            canUndo: this.canUndo(),
            canRedo: this.canRedo()
        });
    }

    /**
     * Check if can undo
     */
    canUndo() {
        return this.historyIndex > 0;
    }

    /**
     * Check if can redo
     */
    canRedo() {
        return this.historyIndex < this.history.length - 1;
    }

    /**
     * Undo last action
     */
    undo() {
        if (this.canUndo()) {
            this.historyIndex--;
            const state = this.history[this.historyIndex];
            this.layers = JSON.parse(JSON.stringify(state.layers));
            this.selectedLayerId = state.selectedLayerId;
            
            this.emit('layersChanged', this.layers);
            this.emit('selectionChanged', this.getSelectedLayer());
            this.emit('historyChanged', {
                canUndo: this.canUndo(),
                canRedo: this.canRedo()
            });
        }
    }

    /**
     * Redo last undone action
     */
    redo() {
        if (this.canRedo()) {
            this.historyIndex++;
            const state = this.history[this.historyIndex];
            this.layers = JSON.parse(JSON.stringify(state.layers));
            this.selectedLayerId = state.selectedLayerId;
            
            this.emit('layersChanged', this.layers);
            this.emit('selectionChanged', this.getSelectedLayer());
            this.emit('historyChanged', {
                canUndo: this.canUndo(),
                canRedo: this.canRedo()
            });
        }
    }

    /**
     * Import state from JSON
     */
    importState(data) {
        this.layers = data.layers || [];
        this.canvas.width = data.width || 250;
        this.canvas.height = data.height || 128;
        this.selectedLayerId = null;
        
        this.saveHistory();
        this.emit('layersChanged', this.layers);
        this.emit('selectionChanged', null);
        this.emit('canvasSizeChanged', this.canvas);
    }

    /**
     * Export state to JSON
     */
    exportState() {
        return {
            width: this.canvas.width,
            height: this.canvas.height,
            layers: this.layers
        };
    }

    /**
     * Set hardware info
     */
    setHardwareInfo(info) {
        this.hardwareInfo = info;
        if (info && info.width && info.height) {
            this.setCanvasSize(info.width, info.height);
        }
        this.emit('hardwareInfoChanged', info);
    }
}

// Create global state instance
const state = new State();