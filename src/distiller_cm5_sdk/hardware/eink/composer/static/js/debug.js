/**
 * Debug utilities for E-ink Composer frontend
 */

class DebugManager {
    constructor() {
        this.enabled = localStorage.getItem('eink_debug') === 'true';
        this.logs = [];
        this.maxLogs = 1000;
        this.performanceMarks = {};
        this.operations = 0;
        this.console = null;
        this.consoleVisible = false;
        
        // Initialize debug console
        this.initConsole();
        
        // Set up keyboard shortcuts
        this.setupKeyboardShortcuts();
        
        // Override console methods when debug is enabled
        if (this.enabled) {
            this.overrideConsoleMethods();
        }
    }
    
    initConsole() {
        // Create debug console container
        const container = document.createElement('div');
        container.id = 'debug-console';
        container.className = 'debug-console';
        container.style.cssText = `
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            height: 200px;
            background: rgba(0, 0, 0, 0.9);
            color: #0f0;
            font-family: monospace;
            font-size: 12px;
            z-index: 10000;
            display: none;
            flex-direction: column;
            border-top: 2px solid #0f0;
        `;
        
        // Add header
        const header = document.createElement('div');
        header.style.cssText = `
            padding: 5px 10px;
            background: rgba(0, 255, 0, 0.1);
            border-bottom: 1px solid #0f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        `;
        header.innerHTML = `
            <span>Debug Console (Press F12 to toggle)</span>
            <div>
                <button id="debug-clear" style="margin-right: 10px;">Clear</button>
                <button id="debug-export">Export</button>
                <button id="debug-close">×</button>
            </div>
        `;
        
        // Add log container
        const logContainer = document.createElement('div');
        logContainer.id = 'debug-logs';
        logContainer.style.cssText = `
            flex: 1;
            overflow-y: auto;
            padding: 5px 10px;
            white-space: pre-wrap;
            word-wrap: break-word;
        `;
        
        container.appendChild(header);
        container.appendChild(logContainer);
        document.body.appendChild(container);
        
        this.console = container;
        this.logContainer = logContainer;
        
        // Set up button handlers
        document.getElementById('debug-clear').onclick = () => this.clearLogs();
        document.getElementById('debug-export').onclick = () => this.exportLogs();
        document.getElementById('debug-close').onclick = () => this.hideConsole();
    }
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // F12 to toggle debug console
            if (e.key === 'F12') {
                e.preventDefault();
                this.toggleConsole();
            }
            
            // Ctrl+Shift+D to toggle debug mode
            if (e.ctrlKey && e.shiftKey && e.key === 'D') {
                e.preventDefault();
                this.toggleDebug();
            }
            
            // Ctrl+Shift+L to dump layer state
            if (e.ctrlKey && e.shiftKey && e.key === 'L') {
                e.preventDefault();
                this.dumpLayerState();
            }
            
            // Ctrl+Shift+P to show performance stats
            if (e.ctrlKey && e.shiftKey && e.key === 'P') {
                e.preventDefault();
                this.showPerformanceStats();
            }
        });
    }
    
    overrideConsoleMethods() {
        const originalLog = console.log;
        const originalError = console.error;
        const originalWarn = console.warn;
        const originalDebug = console.debug;
        
        console.log = (...args) => {
            this.log('LOG', args);
            originalLog.apply(console, args);
        };
        
        console.error = (...args) => {
            this.log('ERROR', args);
            originalError.apply(console, args);
        };
        
        console.warn = (...args) => {
            this.log('WARN', args);
            originalWarn.apply(console, args);
        };
        
        console.debug = (...args) => {
            if (this.enabled) {
                this.log('DEBUG', args);
                originalDebug.apply(console, args);
            }
        };
    }
    
    log(level, args) {
        if (!this.enabled && level === 'DEBUG') return;
        
        const timestamp = new Date().toISOString();
        const message = args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg, null, 2);
                } catch {
                    return String(arg);
                }
            }
            return String(arg);
        }).join(' ');
        
        const logEntry = {
            timestamp,
            level,
            message,
            stack: level === 'ERROR' ? new Error().stack : null
        };
        
        this.logs.push(logEntry);
        
        // Limit log size
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
        }
        
        // Add to console if visible
        if (this.consoleVisible && this.logContainer) {
            this.addLogToConsole(logEntry);
        }
    }
    
    addLogToConsole(logEntry) {
        const logLine = document.createElement('div');
        const levelColors = {
            'LOG': '#0f0',
            'ERROR': '#f00',
            'WARN': '#ff0',
            'DEBUG': '#0ff'
        };
        
        logLine.style.color = levelColors[logEntry.level] || '#0f0';
        logLine.textContent = `[${logEntry.timestamp.split('T')[1].split('.')[0]}] [${logEntry.level}] ${logEntry.message}`;
        
        this.logContainer.appendChild(logLine);
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
    }
    
    toggleDebug() {
        this.enabled = !this.enabled;
        localStorage.setItem('eink_debug', this.enabled.toString());
        
        const status = this.enabled ? 'enabled' : 'disabled';
        Utils.showNotification(`Debug mode ${status}`, 'info');
        console.log(`Debug mode ${status}`);
        
        if (this.enabled) {
            this.overrideConsoleMethods();
            this.showConsole();
        } else {
            this.hideConsole();
        }
        
        // Toggle backend debug mode
        this.toggleBackendDebug(this.enabled);
    }
    
    async toggleBackendDebug(enabled) {
        try {
            const response = await fetch('/api/debug/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            const data = await response.json();
            console.debug('Backend debug mode:', data.message);
        } catch (error) {
            console.error('Failed to toggle backend debug:', error);
        }
    }
    
    toggleConsole() {
        if (this.consoleVisible) {
            this.hideConsole();
        } else {
            this.showConsole();
        }
    }
    
    showConsole() {
        if (!this.console) return;
        
        this.console.style.display = 'flex';
        this.consoleVisible = true;
        
        // Clear and repopulate with recent logs
        this.logContainer.innerHTML = '';
        this.logs.slice(-100).forEach(log => this.addLogToConsole(log));
    }
    
    hideConsole() {
        if (!this.console) return;
        
        this.console.style.display = 'none';
        this.consoleVisible = false;
    }
    
    clearLogs() {
        this.logs = [];
        if (this.logContainer) {
            this.logContainer.innerHTML = '';
        }
        console.debug('Debug logs cleared');
    }
    
    exportLogs() {
        const exportData = {
            timestamp: new Date().toISOString(),
            logs: this.logs,
            performance: this.getPerformanceStats(),
            state: this.getDebugState()
        };
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `eink-debug-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        console.log('Debug logs exported');
    }
    
    // Performance monitoring
    startOperation(name) {
        const key = `${name}_${++this.operations}`;
        this.performanceMarks[key] = performance.now();
        console.debug(`Started operation: ${name} (#${this.operations})`);
        return key;
    }
    
    endOperation(key, details = {}) {
        if (!this.performanceMarks[key]) return;
        
        const duration = performance.now() - this.performanceMarks[key];
        delete this.performanceMarks[key];
        
        console.debug(`Completed operation: ${key} in ${duration.toFixed(2)}ms`, details);
        return duration;
    }
    
    measureFunction(name, fn) {
        return (...args) => {
            const key = this.startOperation(name);
            try {
                const result = fn(...args);
                if (result instanceof Promise) {
                    return result.finally(() => this.endOperation(key));
                }
                this.endOperation(key);
                return result;
            } catch (error) {
                this.endOperation(key, { error: error.message });
                throw error;
            }
        };
    }
    
    // State inspection
    dumpLayerState() {
        if (!window.state) {
            console.error('State object not available');
            return;
        }
        
        const stateInfo = {
            layers: state.layers.map(layer => ({
                id: layer.id,
                type: layer.type,
                visible: layer.visible,
                position: { x: layer.x, y: layer.y },
                size: layer.width ? { width: layer.width, height: layer.height } : undefined,
                data: layer.text || layer.imagePath || null
            })),
            selectedLayers: Array.from(state.selectedLayers || []),
            currentTool: state.currentTool,
            canvasSize: { width: state.canvasWidth, height: state.canvasHeight }
        };
        
        console.log('Layer State Dump:', stateInfo);
        
        // Also fetch backend state if debug is enabled
        if (this.enabled) {
            this.fetchBackendDebugState();
        }
    }
    
    async fetchBackendDebugState() {
        try {
            const response = await fetch('/api/debug/layers');
            const data = await response.json();
            console.log('Backend State:', data);
        } catch (error) {
            console.error('Failed to fetch backend state:', error);
        }
    }
    
    showPerformanceStats() {
        this.fetchBackendPerformance().then(stats => {
            console.log('Performance Statistics:', stats);
        });
    }
    
    async fetchBackendPerformance() {
        try {
            const response = await fetch('/api/debug/status');
            return await response.json();
        } catch (error) {
            console.error('Failed to fetch performance stats:', error);
            return null;
        }
    }
    
    getPerformanceStats() {
        return {
            operations: this.operations,
            pendingOperations: Object.keys(this.performanceMarks).length,
            logCount: this.logs.length
        };
    }
    
    getDebugState() {
        return {
            enabled: this.enabled,
            consoleVisible: this.consoleVisible,
            operations: this.operations,
            logCount: this.logs.length
        };
    }
    
    // Canvas debugging
    drawDebugOverlay(ctx, canvas) {
        if (!this.enabled) return;
        
        ctx.save();
        ctx.strokeStyle = 'rgba(255, 0, 0, 0.5)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        
        // Draw canvas bounds
        ctx.strokeRect(0, 0, canvas.width, canvas.height);
        
        // Draw center lines
        ctx.beginPath();
        ctx.moveTo(canvas.width / 2, 0);
        ctx.lineTo(canvas.width / 2, canvas.height);
        ctx.moveTo(0, canvas.height / 2);
        ctx.lineTo(canvas.width, canvas.height / 2);
        ctx.stroke();
        
        // Draw dimensions
        ctx.fillStyle = 'rgba(255, 0, 0, 0.8)';
        ctx.font = '10px monospace';
        ctx.fillText(`${canvas.width}×${canvas.height}`, 5, 15);
        
        ctx.restore();
    }
    
    // Network request logging
    logRequest(method, url, data = null) {
        if (!this.enabled) return;
        
        console.debug(`API Request: ${method} ${url}`, data);
    }
    
    logResponse(method, url, status, data = null) {
        if (!this.enabled) return;
        
        const level = status >= 400 ? 'ERROR' : 'DEBUG';
        console[level.toLowerCase()](`API Response: ${method} ${url} - ${status}`, data);
    }
}

// Create global debug manager instance
window.debugManager = new DebugManager();

// Export for use in other modules
window.DebugManager = DebugManager;