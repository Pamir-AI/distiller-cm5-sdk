/**
 * Tool management for the E-ink Composer
 */

const Tools = {
    currentTool: 'select',
    isDrawing: false,
    startPoint: null,
    
    init() {
        this.setupToolButtons();
        this.setupKeyboardShortcuts();
        this.setupSpecialTools();
    },
    
    setupToolButtons() {
        const toolButtons = document.querySelectorAll('.tool-btn');
        
        toolButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const tool = btn.dataset.tool;
                this.setTool(tool);
            });
        });
    },
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            switch(e.key.toLowerCase()) {
                case 'v':
                    this.setTool('select');
                    break;
                case 't':
                    this.setTool('text');
                    break;
                case 'r':
                    this.setTool('rectangle');
                    break;
                case 'i':
                    this.setTool('image');
                    break;
                case 'delete':
                case 'backspace':
                    if (e.target.tagName !== 'INPUT') {
                        this.deleteSelectedLayer();
                        e.preventDefault();
                    }
                    break;
                case 'z':
                    if (e.ctrlKey || e.metaKey) {
                        if (e.shiftKey) {
                            state.redo();
                        } else {
                            state.undo();
                        }
                        e.preventDefault();
                    }
                    break;
                case 'y':
                    if (e.ctrlKey || e.metaKey) {
                        state.redo();
                        e.preventDefault();
                    }
                    break;
                case 'a':
                    if (e.ctrlKey || e.metaKey) {
                        this.selectAll();
                        e.preventDefault();
                    }
                    break;
                case 'escape':
                    this.setTool('select');
                    state.selectLayer(null);
                    break;
            }
        });
    },
    
    setTool(tool) {
        this.currentTool = tool;
        state.setTool(tool);
        
        // Update UI
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tool === tool);
        });
        
        // Update cursor style
        this.updateCursor(tool);
        
        // Handle special tools that need immediate action
        if (tool === 'image') {
            this.handleImageTool();
        } else if (tool === 'ip' || tool === 'qr') {
            // These will be handled on canvas click
            Utils.showNotification(`Click on canvas to place ${tool.toUpperCase()}`, 'info');
        } else if (tool === 'text') {
            Utils.showNotification('Click on canvas to place text', 'info');
        } else if (tool === 'rectangle') {
            Utils.showNotification('Click and drag to draw rectangle', 'info');
        }
    },
    
    updateCursor(tool) {
        const canvas = document.getElementById('selectionCanvas');
        switch(tool) {
            case 'select':
                canvas.style.cursor = 'default';
                break;
            case 'text':
                canvas.style.cursor = 'text';
                break;
            case 'rectangle':
                canvas.style.cursor = 'crosshair';
                break;
            case 'image':
            case 'ip':
            case 'qr':
                canvas.style.cursor = 'copy';
                break;
            default:
                canvas.style.cursor = 'default';
        }
    },
    
    handleImageTool() {
        const input = document.getElementById('imageInput');
        input.click();
        
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (file) {
                try {
                    // Calculate centered position and auto-scale
                    const canvasWidth = state.canvasSize.width || 250;
                    const canvasHeight = state.canvasSize.height || 128;
                    
                    // Create temporary image to get dimensions
                    const img = new Image();
                    const reader = new FileReader();
                    
                    reader.onload = async (event) => {
                        img.src = event.target.result;
                        img.onload = async () => {
                            // Calculate scale to fit within canvas
                            const scale = Math.min(
                                canvasWidth / img.width,
                                canvasHeight / img.height,
                                1 // Don't upscale
                            );
                            
                            const width = Math.floor(img.width * scale);
                            const height = Math.floor(img.height * scale);
                            const x = Math.floor((canvasWidth - width) / 2);
                            const y = Math.floor((canvasHeight - height) / 2);
                            
                            // Upload image with calculated dimensions
                            const response = await API.addImageLayer(file, x, y, width, height);
                            if (response.success) {
                                await canvasManager.loadLayersFromServer();
                                Utils.showNotification('Image added', 'success');
                            }
                        };
                    };
                    reader.readAsDataURL(file);
                } catch (error) {
                    Utils.showNotification('Failed to add image', 'error');
                }
            }
            
            // Clear input and switch back to select
            input.value = '';
            this.setTool('select');
        };
    },
    
    setupSpecialTools() {
        // Setup drag and drop for images
        const canvas = document.getElementById('selectionCanvas');
        
        canvas.addEventListener('dragover', (e) => {
            e.preventDefault();
            canvas.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
        });
        
        canvas.addEventListener('dragleave', (e) => {
            e.preventDefault();
            canvas.style.backgroundColor = 'transparent';
        });
        
        canvas.addEventListener('drop', async (e) => {
            e.preventDefault();
            canvas.style.backgroundColor = 'transparent';
            
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type.startsWith('image/')) {
                const file = files[0];
                const pos = canvasManager.getMousePos(e);
                
                try {
                    const response = await API.addImageLayer(file, pos.x, pos.y);
                    if (response.success) {
                        await canvasManager.loadLayersFromServer();
                        Utils.showNotification('Image dropped', 'success');
                    }
                } catch (error) {
                    Utils.showNotification('Failed to add image', 'error');
                }
            }
        });
    },
    
    deleteSelectedLayer() {
        const selectedLayer = state.getSelectedLayer();
        if (selectedLayer) {
            if (confirm('Delete this layer?')) {
                state.removeLayer(selectedLayer.id);
                // Also delete from server
                API.deleteLayer(selectedLayer.id).catch(console.error);
            }
        }
    },
    
    selectAll() {
        // Not implemented for single selection mode
        // Could be enhanced for multi-selection
    }
};