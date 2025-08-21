/**
 * Main application entry point for E-ink Composer
 */

let canvasManager = null;

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    console.log('E-ink Composer v2.0 - Initializing...');
    
    try {
        // Initialize canvas manager
        const mainCanvas = document.getElementById('mainCanvas');
        const gridCanvas = document.getElementById('gridCanvas');
        const selectionCanvas = document.getElementById('selectionCanvas');
        
        canvasManager = new CanvasManager(mainCanvas, gridCanvas, selectionCanvas);
        
        // Initialize UI
        UI.init();
        
        // Initialize tools
        Tools.init();
        
        // Get hardware status
        await initializeHardware();
        
        // Load initial layers from server
        await loadInitialData();
        
        console.log('E-ink Composer initialized successfully');
        
    } catch (error) {
        console.error('Failed to initialize application:', error);
        alert('Failed to initialize application. Please refresh the page.');
    }
});

/**
 * Initialize hardware and get display info
 */
async function initializeHardware() {
    try {
        const status = await API.getHardwareStatus();
        console.log('Hardware status:', status);
        
        if (status.available) {
            state.setHardwareInfo(status);
            
            // Update UI with hardware info
            if (status.width && status.height) {
                document.getElementById('canvasSize').textContent = `${status.width}×${status.height}`;
            }
            
            Utils.showNotification(`Hardware connected: ${status.firmware || 'Unknown firmware'}`, 'success');
        } else {
            Utils.showNotification('Hardware not available - preview mode only', 'warning');
        }
    } catch (error) {
        console.error('Failed to get hardware status:', error);
        Utils.showNotification('Failed to connect to hardware', 'error');
    }
}

/**
 * Load initial data from server
 */
async function loadInitialData() {
    try {
        // Clear any existing layers (including invalid ones from previous sessions)
        state.clearLayers();
        
        // Load existing layers from server
        const layers = await API.getLayers();
        console.log('Loaded layers:', layers);
        
        // Convert server data to layer objects
        layers.forEach(layerData => {
            const layer = createLayerFromData(layerData);
            // Only add layers with valid server IDs
            if (layer.id && !layer.id.toString().includes('_')) {
                state.addLayer(layer);
            } else {
                console.warn(`Skipping invalid layer ${layer.id} from server`);
            }
        });
        
        // Initial render
        canvasManager.render();
        
    } catch (error) {
        console.error('Failed to load initial data:', error);
        // Clear any invalid layers and start with empty canvas
        state.clearLayers();
        canvasManager.render();
    }
}

/**
 * Global error handler
 */
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    Utils.showNotification('An error occurred. Please check the console.', 'error');
});

/**
 * Handle window resize
 */
window.addEventListener('resize', Utils.debounce(() => {
    // Could implement responsive canvas scaling here
}, 250));

/**
 * Prevent accidental navigation
 */
window.addEventListener('beforeunload', (e) => {
    if (state.layers.length > 0) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
    }
});

/**
 * Export functions for debugging
 */
window.EinkComposer = {
    state,
    canvasManager,
    API,
    Utils,
    Tools,
    UI,
    version: '2.0.0',
    
    // Debug functions
    debug: {
        getLayers: () => state.getLayers(),
        getSelectedLayer: () => state.getSelectedLayer(),
        clearAll: () => {
            state.clearLayers();
            canvasManager.render();
        },
        exportState: () => state.exportState(),
        importState: (data) => {
            state.importState(data);
            canvasManager.render();
        }
    }
};

console.log('E-ink Composer loaded. Access debug functions via window.EinkComposer.debug');