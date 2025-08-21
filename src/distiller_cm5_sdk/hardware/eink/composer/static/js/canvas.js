/**
 * Canvas management for the E-ink Composer
 */

class CanvasManager {
    constructor(mainCanvas, gridCanvas, selectionCanvas) {
        this.mainCanvas = mainCanvas;
        this.gridCanvas = gridCanvas;
        this.selectionCanvas = selectionCanvas;
        
        this.mainCtx = mainCanvas.getContext('2d');
        this.gridCtx = gridCanvas.getContext('2d');
        this.selectionCtx = selectionCanvas.getContext('2d');
        
        this.width = 250;
        this.height = 128;
        this.scale = 2; // Scale for better visibility
        
        this.selection = null;
        this.dragOffset = { x: 0, y: 0 };
        this.isResizing = false;
        this.resizeHandle = null;
        
        // Multi-selection support
        this.selectedLayers = new Set();
        this.selectionBox = null;
        this.isSelecting = false;
        this.selectionStart = null;
        
        // Text editing
        this.editingLayer = null;
        this.textInput = null;
        
        this.init();
        this.setupEventListeners();
    }

    init() {
        // Set canvas dimensions
        this.setSize(this.width, this.height);
        
        // Subscribe to state changes
        state.subscribe('layersChanged', () => this.render());
        state.subscribe('selectionChanged', (layer) => this.updateSelection(layer));
        state.subscribe('canvasSizeChanged', ({ width, height }) => {
            this.setSize(width, height);
        });
        state.subscribe('gridChanged', () => this.drawGrid());
    }

    setSize(width, height) {
        this.width = width;
        this.height = height;
        
        // Set actual canvas size with scale
        const actualWidth = width * this.scale;
        const actualHeight = height * this.scale;
        
        [this.mainCanvas, this.gridCanvas, this.selectionCanvas].forEach(canvas => {
            canvas.width = actualWidth;
            canvas.height = actualHeight;
            canvas.style.width = `${actualWidth}px`;
            canvas.style.height = `${actualHeight}px`;
        });
        
        // Scale contexts for crisp rendering
        this.mainCtx.scale(this.scale, this.scale);
        this.gridCtx.scale(this.scale, this.scale);
        this.selectionCtx.scale(this.scale, this.scale);
        
        this.render();
    }

    setupEventListeners() {
        this.selectionCanvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.selectionCanvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.selectionCanvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.selectionCanvas.addEventListener('dblclick', (e) => this.handleDoubleClick(e));
        
        // Touch events for mobile
        this.selectionCanvas.addEventListener('touchstart', (e) => this.handleTouchStart(e));
        this.selectionCanvas.addEventListener('touchmove', (e) => this.handleTouchMove(e));
        this.selectionCanvas.addEventListener('touchend', (e) => this.handleTouchEnd(e));
    }

    render() {
        // Clear canvas
        this.mainCtx.clearRect(0, 0, this.width, this.height);
        
        // Draw white background
        this.mainCtx.fillStyle = 'white';
        this.mainCtx.fillRect(0, 0, this.width, this.height);
        
        // Draw layers
        const layers = state.getLayers();
        layers.forEach(layer => {
            // Skip layers with invalid IDs (temp or locally generated)
            if (layer.id && layer.id.toString().includes('_')) {
                console.debug(`Skipping invalid layer ${layer.id} in render`);
                return;
            }
            if (layer.visible) {
                layer.draw(this.mainCtx);
            }
        });
        
        // Draw grid if enabled
        if (state.grid.enabled) {
            this.drawGrid();
        }
        
        // Update selection
        this.drawSelection();
    }

    drawGrid() {
        this.gridCtx.clearRect(0, 0, this.width, this.height);
        
        if (!state.grid.enabled) return;
        
        const gridSize = state.grid.size;
        
        this.gridCtx.strokeStyle = 'rgba(0, 0, 0, 0.1)';
        this.gridCtx.lineWidth = 0.5;
        
        // Vertical lines
        for (let x = gridSize; x < this.width; x += gridSize) {
            this.gridCtx.beginPath();
            this.gridCtx.moveTo(x, 0);
            this.gridCtx.lineTo(x, this.height);
            this.gridCtx.stroke();
        }
        
        // Horizontal lines
        for (let y = gridSize; y < this.height; y += gridSize) {
            this.gridCtx.beginPath();
            this.gridCtx.moveTo(0, y);
            this.gridCtx.lineTo(this.width, y);
            this.gridCtx.stroke();
        }
    }

    drawSelection() {
        this.selectionCtx.clearRect(0, 0, this.width, this.height);
        
        // Draw multi-selection if exists
        if (this.selectedLayers.size > 0) {
            const layers = state.getLayers();
            this.selectedLayers.forEach(layerId => {
                const layer = layers.find(l => l.id === layerId);
                if (layer) {
                    const bounds = layer.getBounds();
                    
                    // Draw selection rectangle with different style for multi-select
                    this.selectionCtx.strokeStyle = 'rgba(59, 130, 246, 0.8)';
                    this.selectionCtx.lineWidth = 2;
                    this.selectionCtx.setLineDash([5, 3]);
                    this.selectionCtx.strokeRect(bounds.x, bounds.y, bounds.width, bounds.height);
                    this.selectionCtx.setLineDash([]);
                }
            });
        } else {
            // Draw single selection
            const selectedLayer = state.getSelectedLayer();
            if (!selectedLayer) return;
            
            const bounds = selectedLayer.getBounds();
            
            // Draw selection rectangle
            this.selectionCtx.strokeStyle = '#3b82f6';
            this.selectionCtx.lineWidth = 1;
            this.selectionCtx.strokeRect(bounds.x, bounds.y, bounds.width, bounds.height);
            
            // Draw resize handles only for single selection
            const handles = this.getResizeHandles(bounds);
            this.selectionCtx.fillStyle = '#3b82f6';
            
            Object.values(handles).forEach(handle => {
                this.selectionCtx.fillRect(handle.x - 3, handle.y - 3, 6, 6);
            });
        }
    }

    getResizeHandles(bounds) {
        return {
            nw: { x: bounds.x, y: bounds.y },
            ne: { x: bounds.x + bounds.width, y: bounds.y },
            sw: { x: bounds.x, y: bounds.y + bounds.height },
            se: { x: bounds.x + bounds.width, y: bounds.y + bounds.height },
            n: { x: bounds.x + bounds.width / 2, y: bounds.y },
            s: { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height },
            w: { x: bounds.x, y: bounds.y + bounds.height / 2 },
            e: { x: bounds.x + bounds.width, y: bounds.y + bounds.height / 2 }
        };
    }

    getMousePos(evt) {
        const rect = this.mainCanvas.getBoundingClientRect();
        return {
            x: Math.round((evt.clientX - rect.left) / this.scale),
            y: Math.round((evt.clientY - rect.top) / this.scale)
        };
    }

    handleMouseDown(e) {
        const pos = this.getMousePos(e);
        const tool = state.tool;
        
        if (tool === 'select') {
            const layerAtPoint = this.getLayerAtPoint(pos);
            
            if (e.ctrlKey || e.metaKey) {
                // Add/remove from selection
                this.handleMultiSelection(pos, true);
            } else if (!layerAtPoint) {
                // Click in empty space - start rubber band selection
                this.startRubberBandSelection(pos);
            } else {
                // Click on a layer - normal selection
                this.handleSelection(pos);
            }
        } else if (tool === 'text') {
            this.createTextLayer(pos);
        } else if (tool === 'rectangle') {
            this.startRectangle(pos);
        } else if (tool === 'ip') {
            this.addIPPlaceholder(pos);
        } else if (tool === 'qr') {
            this.addQRPlaceholder(pos);
        }
    }

    handleMouseMove(e) {
        const pos = this.getMousePos(e);
        
        // Update cursor position
        document.getElementById('cursorPos').textContent = `${Math.round(pos.x)}, ${Math.round(pos.y)}`;
        
        if (this.isSelecting && state.tool === 'select') {
            // Update rubber band selection
            if (this.selectionBox && this.selectionStart) {
                this.selectionBox.width = pos.x - this.selectionStart.x;
                this.selectionBox.height = pos.y - this.selectionStart.y;
                this.updateRubberBandSelection();
                this.drawRubberBand();
            }
        } else if (state.isDragging && state.tool === 'select') {
            const selectedLayer = state.getSelectedLayer();
            if (selectedLayer && !selectedLayer.locked) {
                let newX = pos.x - this.dragOffset.x;
                let newY = pos.y - this.dragOffset.y;
                
                // Apply snapping
                if (state.snap.enabled) {
                    newX = Utils.snapToGrid(newX, state.grid.size);
                    newY = Utils.snapToGrid(newY, state.grid.size);
                }
                
                // Floor coordinates to ensure integers
                selectedLayer.setPosition(Math.floor(newX), Math.floor(newY));
                this.render();
            }
        } else if (this.isResizing && state.tool === 'rectangle') {
            // Handle rectangle drawing
            const rect = state.getSelectedLayer();
            if (rect && rect.type === 'rectangle') {
                rect.width = Math.floor(Math.abs(pos.x - rect.x));
                rect.height = Math.floor(Math.abs(pos.y - rect.y));
                this.render();
            }
        }
    }

    handleMouseUp(e) {
        if (this.isSelecting) {
            // Finalize rubber band selection
            this.isSelecting = false;
            this.selectionBox = null;
            this.selectionStart = null;
            // Clear the rubber band visual
            this.selectionCtx.clearRect(0, 0, this.width, this.height);
            // The selection is already updated in updateRubberBandSelection
        } else if (state.isDragging) {
            state.isDragging = false;
            // Save state after dragging
            const selectedLayer = state.getSelectedLayer();
            if (selectedLayer) {
                state.saveHistory();
                // Sync position to server with floored coordinates
                API.updateLayer(selectedLayer.id, { 
                    x: Math.floor(selectedLayer.x), 
                    y: Math.floor(selectedLayer.y) 
                }).catch(error => {
                    console.error('Failed to update layer position:', error);
                });
            }
        }
        
        if (this.isResizing && state.tool === 'rectangle') {
            // Finalize rectangle creation
            const tempRect = state.getSelectedLayer();
            if (tempRect && tempRect.id === 'temp_rect') {
                // Create the rectangle on the server
                API.addRectangleLayer({
                    x: Math.floor(tempRect.x),
                    y: Math.floor(tempRect.y),
                    width: Math.floor(Math.max(tempRect.width, 1)),
                    height: Math.floor(Math.max(tempRect.height, 1)),
                    filled: false
                }).then(response => {
                    if (response.success && response.layer_id) {
                        // Remove temp rectangle
                        state.removeLayer('temp_rect');
                        // Create proper rectangle with server ID
                        const rect = new RectangleLayer(response.layer_id, tempRect.x, tempRect.y, tempRect.width, tempRect.height);
                        rect.filled = false;
                        state.addLayer(rect);
                        state.selectLayer(rect.id);
                        this.render();
                    } else {
                        console.error('Failed to create rectangle:', response);
                        state.removeLayer('temp_rect');
                        this.render();
                    }
                }).catch(error => {
                    console.error('Error creating rectangle:', error);
                    state.removeLayer('temp_rect');
                    this.render();
                });
            }
            
            this.isResizing = false;
            state.setTool('select');
        } else if (this.isResizing) {
            this.isResizing = false;
            state.saveHistory();
        }
    }

    handleDoubleClick(e) {
        const pos = this.getMousePos(e);
        const layer = this.getLayerAtPoint(pos);
        
        if (layer && layer.type === 'text') {
            // Start inline text editing
            this.startInlineTextEdit(layer);
        }
    }

    handleSelection(pos) {
        const layer = this.getLayerAtPoint(pos);
        
        if (layer) {
            // Clear multi-selection if exists
            this.selectedLayers.clear();
            
            state.selectLayer(layer.id);
            state.isDragging = true;
            this.dragOffset = {
                x: pos.x - layer.x,
                y: pos.y - layer.y
            };
        } else {
            state.selectLayer(null);
            this.selectedLayers.clear();
        }
    }
    
    handleMultiSelection(pos, addToSelection) {
        const layer = this.getLayerAtPoint(pos);
        
        if (layer) {
            if (addToSelection) {
                // Toggle layer in selection
                if (this.selectedLayers.has(layer.id)) {
                    this.selectedLayers.delete(layer.id);
                } else {
                    this.selectedLayers.add(layer.id);
                }
            } else {
                this.selectedLayers.clear();
                this.selectedLayers.add(layer.id);
            }
            
            // Update visual selection
            this.drawSelection();
        }
    }
    
    startRubberBandSelection(pos) {
        this.isSelecting = true;
        this.selectionStart = pos;
        this.selectionBox = {
            x: pos.x,
            y: pos.y,
            width: 0,
            height: 0
        };
    }

    createTextLayer(pos) {
        // Create text layer on server first
        API.addTextLayer({
            text: 'Text',  // Default text (required by backend)
            x: Math.floor(pos.x),
            y: Math.floor(pos.y)
        }).then(response => {
            if (response.success && response.layer_id) {
                // Create local layer with server ID
                const layer = new TextLayer(response.layer_id, 'Text', pos.x, pos.y);
                state.addLayer(layer);
                state.selectLayer(layer.id);
                
                // Start inline editing immediately
                this.startInlineTextEdit(layer);
            } else {
                console.error('Failed to create text layer:', response);
                Utils.showNotification('Failed to create text layer', 'error');
            }
        }).catch(error => {
            console.error('Error creating text layer:', error);
            Utils.showNotification('Error creating text layer', 'error');
        });
    }
    
    startInlineTextEdit(layer) {
        if (this.textInput) {
            this.finishTextEdit();
        }
        
        this.editingLayer = layer;
        
        // Create an input element positioned over the text
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'inline-text-input';
        input.value = layer.text || '';
        input.style.position = 'absolute';
        input.style.left = `${layer.x * this.scale}px`;
        input.style.top = `${layer.y * this.scale}px`;
        input.style.fontSize = `${12 * this.scale * (layer.fontSize || 1)}px`;
        input.style.fontFamily = 'monospace';
        input.style.border = '1px solid #3b82f6';
        input.style.padding = '2px';
        input.style.background = 'white';
        input.style.zIndex = '1000';
        
        const canvasContainer = this.selectionCanvas.parentElement;
        canvasContainer.appendChild(input);
        
        this.textInput = input;
        
        // Focus and select all
        input.focus();
        input.select();
        
        // Handle input events
        input.addEventListener('input', () => {
            layer.text = input.value;
            this.render();
        });
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === 'Escape') {
                this.finishTextEdit();
                e.preventDefault();
            }
        });
        
        input.addEventListener('blur', () => {
            this.finishTextEdit();
        });
    }
    
    finishTextEdit() {
        if (!this.textInput || !this.editingLayer) return;
        
        const layer = this.editingLayer;
        const text = this.textInput.value.trim();
        
        if (text && text !== layer.text) {
            layer.text = text;
            // Update on server
            API.updateLayer(layer.id, { text: text }).catch(error => {
                console.error('Failed to update text:', error);
                Utils.showNotification('Failed to update text', 'error');
            });
        } else if (!text) {
            // Remove empty text layer from server first, then local
            API.deleteLayer(layer.id).then(() => {
                state.removeLayer(layer.id);
            }).catch(error => {
                console.error('Failed to delete empty layer:', error);
                // Remove locally anyway if server delete fails
                state.removeLayer(layer.id);
            });
        }
        
        // Remove input element
        this.textInput.remove();
        this.textInput = null;
        this.editingLayer = null;
        
        // Switch back to select tool
        Tools.setTool('select');
        
        this.render();
    }

    startRectangle(pos) {
        // Store the starting position for rectangle drawing
        this.rectangleStart = pos;
        this.isResizing = true;
        
        // Create a temporary local rectangle for drawing feedback
        const tempRect = new RectangleLayer('temp_rect', pos.x, pos.y, 1, 1);
        tempRect.filled = false;
        state.addLayer(tempRect);
        state.selectLayer(tempRect.id);
    }

    addIPPlaceholder(pos) {
        // Create IP placeholder on server
        API.addPlaceholder('ip', Math.floor(pos.x), Math.floor(pos.y)).then(response => {
            if (response.success && response.layer_id) {
                // Reload from server to get actual IP
                this.loadLayersFromServer();
            } else {
                console.error('Failed to create IP placeholder:', response);
                Utils.showNotification('Failed to add IP address', 'error');
            }
        }).catch(error => {
            console.error('Error creating IP placeholder:', error);
            Utils.showNotification('Error adding IP address', 'error');
        });
        state.setTool('select');
    }

    addQRPlaceholder(pos) {
        // Create QR placeholder on server
        API.addPlaceholder('qr', Math.floor(pos.x), Math.floor(pos.y), { width: 70, height: 70 }).then(response => {
            if (response.success && response.layer_id) {
                // Reload from server to get the QR code
                this.loadLayersFromServer();
            } else {
                console.error('Failed to create QR placeholder:', response);
                Utils.showNotification('Failed to add QR code', 'error');
            }
        }).catch(error => {
            console.error('Error creating QR placeholder:', error);
            Utils.showNotification('Error adding QR code', 'error');
        });
        state.setTool('select');
    }

    getLayerAtPoint(pos) {
        const layers = state.getLayers();
        
        // Check layers in reverse order (top to bottom)
        for (let i = layers.length - 1; i >= 0; i--) {
            const layer = layers[i];
            if (layer.visible && layer.hitTest(pos.x, pos.y)) {
                return layer;
            }
        }
        
        return null;
    }

    updateSelection(layer) {
        this.drawSelection();
    }

    async loadLayersFromServer() {
        try {
            const layers = await API.getLayers();
            state.clearLayers();
            
            layers.forEach(layerData => {
                const layer = createLayerFromData(layerData);
                state.addLayer(layer);
            });
            
            this.render();
        } catch (error) {
            console.error('Failed to load layers:', error);
        }
    }

    drawRubberBand() {
        this.selectionCtx.clearRect(0, 0, this.width, this.height);
        
        if (!this.selectionBox) return;
        
        // Draw selection rectangle
        this.selectionCtx.strokeStyle = 'rgba(59, 130, 246, 0.5)';
        this.selectionCtx.fillStyle = 'rgba(59, 130, 246, 0.1)';
        this.selectionCtx.lineWidth = 1;
        this.selectionCtx.setLineDash([5, 5]);
        
        const x = Math.min(this.selectionBox.x, this.selectionBox.x + this.selectionBox.width);
        const y = Math.min(this.selectionBox.y, this.selectionBox.y + this.selectionBox.height);
        const width = Math.abs(this.selectionBox.width);
        const height = Math.abs(this.selectionBox.height);
        
        this.selectionCtx.fillRect(x, y, width, height);
        this.selectionCtx.strokeRect(x, y, width, height);
        this.selectionCtx.setLineDash([]);
    }
    
    updateRubberBandSelection() {
        if (!this.selectionBox) return;
        
        const x = Math.min(this.selectionBox.x, this.selectionBox.x + this.selectionBox.width);
        const y = Math.min(this.selectionBox.y, this.selectionBox.y + this.selectionBox.height);
        const width = Math.abs(this.selectionBox.width);
        const height = Math.abs(this.selectionBox.height);
        
        const selectionRect = { x, y, width, height };
        
        // Clear previous selection
        this.selectedLayers.clear();
        
        // Find all layers within the selection box
        const layers = state.getLayers();
        layers.forEach(layer => {
            const bounds = layer.getBounds();
            if (this.rectsIntersect(selectionRect, bounds)) {
                this.selectedLayers.add(layer.id);
            }
        });
        
        // Update state selection if any layers are selected
        if (this.selectedLayers.size > 0) {
            // Select the first layer in the set
            const firstLayerId = Array.from(this.selectedLayers)[0];
            state.selectLayer(firstLayerId);
        } else {
            state.selectLayer(null);
        }
        
        // Highlight selected layers
        this.drawSelection();
    }
    
    rectsIntersect(rect1, rect2) {
        return !(rect1.x > rect2.x + rect2.width ||
                rect1.x + rect1.width < rect2.x ||
                rect1.y > rect2.y + rect2.height ||
                rect1.y + rect1.height < rect2.y);
    }

    // Touch event handlers
    handleTouchStart(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousedown', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.handleMouseDown(mouseEvent);
    }

    handleTouchMove(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousemove', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.handleMouseMove(mouseEvent);
    }

    handleTouchEnd(e) {
        e.preventDefault();
        const mouseEvent = new MouseEvent('mouseup', {});
        this.handleMouseUp(mouseEvent);
    }
}