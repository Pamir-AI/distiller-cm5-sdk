/**
 * API client for backend communication
 */

const API = {
    baseURL: '/api',

    /**
     * Make a request to the API with retry logic and better error handling
     */
    async request(endpoint, options = {}, retries = 3) {
        // Log request if debug is enabled
        if (window.debugManager) {
            window.debugManager.logRequest(options.method || 'GET', `${this.baseURL}${endpoint}`, options.body);
        }
        
        let lastError;
        for (let attempt = 1; attempt <= retries; attempt++) {
            try {
                const response = await fetch(`${this.baseURL}${endpoint}`, {
                    headers: {
                        'Content-Type': 'application/json',
                        ...options.headers
                    },
                    ...options
                });

                if (!response.ok) {
                    const error = await response.json().catch(() => ({}));
                    if (window.debugManager) {
                        window.debugManager.logResponse(options.method || 'GET', `${this.baseURL}${endpoint}`, response.status, error);
                    }
                    
                    // Don't retry client errors (4xx)
                    if (response.status >= 400 && response.status < 500) {
                        const errorMsg = this.getErrorMessage(response.status, error.detail);
                        throw new Error(errorMsg);
                    }
                    
                    // Retry server errors (5xx)
                    if (response.status >= 500 && attempt < retries) {
                        await this.delay(1000 * attempt); // Exponential backoff
                        continue;
                    }
                    
                    throw new Error(error.detail || `HTTP ${response.status}`);
                }

                const data = await response.json();
                
                // Log successful response
                if (window.debugManager) {
                    window.debugManager.logResponse(options.method || 'GET', `${this.baseURL}${endpoint}`, response.status, data);
                }
                
                return data;
            } catch (error) {
                lastError = error;
                
                // Network errors - retry
                if (error.name === 'TypeError' && error.message.includes('fetch') && attempt < retries) {
                    await this.delay(1000 * attempt);
                    continue;
                }
                
                // Don't retry other errors
                console.error('API Error:', error);
                if (window.debugManager) {
                    window.debugManager.log('ERROR', ['API Error:', error.message, error.stack]);
                }
                throw error;
            }
        }
        
        throw lastError;
    },
    
    /**
     * Helper to delay for retries
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },
    
    /**
     * Get user-friendly error message
     */
    getErrorMessage(status, detail) {
        const messages = {
            400: 'Invalid request: ',
            401: 'Authentication required',
            403: 'Permission denied',
            404: 'Resource not found: ',
            422: 'Validation error: ',
            500: 'Server error: ',
            502: 'Service temporarily unavailable',
            503: 'Service overloaded',
        };
        
        const baseMsg = messages[status] || `Error ${status}: `;
        return detail ? baseMsg + detail : baseMsg + 'Unknown error';
    },

    // Layer Management
    async getLayers() {
        return this.request('/layers');
    },

    async addTextLayer(data) {
        try {
            return await this.request('/layers/text', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        } catch (error) {
            Utils.showNotification(`Failed to add text layer: ${error.message}`, 'error');
            throw error;
        }
    },

    async addRectangleLayer(data) {
        try {
            return await this.request('/layers/rectangle', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        } catch (error) {
            Utils.showNotification(`Failed to add rectangle: ${error.message}`, 'error');
            throw error;
        }
    },

    async addImageLayer(file, x = 0, y = 0, width = null, height = null) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('x', x);
        formData.append('y', y);
        if (width) formData.append('width', width);
        if (height) formData.append('height', height);

        if (window.debugManager) {
            window.debugManager.logRequest('POST', `${this.baseURL}/layers/image`, `File: ${file.name}, Position: (${x}, ${y})`);
        }

        const response = await fetch(`${this.baseURL}/layers/image`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            if (window.debugManager) {
                window.debugManager.logResponse('POST', `${this.baseURL}/layers/image`, response.status, 'Failed');
            }
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        if (window.debugManager) {
            window.debugManager.logResponse('POST', `${this.baseURL}/layers/image`, response.status, data);
        }
        return data;
    },

    async addPlaceholder(type, x = 0, y = 0, options = {}) {
        try {
            return await this.request('/layers/placeholder', {
                method: 'POST',
                body: JSON.stringify({
                    placeholder_type: type,
                    x,
                    y,
                    ...options
                })
            });
        } catch (error) {
            const placeholderName = type === 'ip' ? 'IP address' : 'QR code';
            Utils.showNotification(`Failed to add ${placeholderName}: ${error.message}`, 'error');
            throw error;
        }
    },

    async updateLayer(layerId, updates) {
        try {
            return await this.request(`/layers/${layerId}`, {
                method: 'PUT',
                body: JSON.stringify(updates)
            });
        } catch (error) {
            Utils.showNotification(`Failed to update layer: ${error.message}`, 'error');
            throw error;
        }
    },

    async deleteLayer(layerId) {
        try {
            return await this.request(`/layers/${layerId}`, {
                method: 'DELETE'
            });
        } catch (error) {
            Utils.showNotification(`Failed to delete layer: ${error.message}`, 'error');
            throw error;
        }
    },

    async toggleLayer(layerId) {
        return this.request(`/layers/${layerId}/toggle`, {
            method: 'POST'
        });
    },

    async reorderLayer(layerId, newIndex) {
        return this.request(`/layers/${layerId}/reorder`, {
            method: 'POST',
            body: JSON.stringify({ new_index: newIndex })
        });
    },

    async clearAllLayers() {
        return this.request('/layers', {
            method: 'DELETE'
        });
    },

    // Rendering
    async getPreview() {
        return this.request('/preview');
    },

    async render(format = 'png', backgroundColor = 255) {
        return this.request('/render', {
            method: 'POST',
            body: JSON.stringify({
                format,
                background_color: backgroundColor
            })
        });
    },

    // Hardware
    async displayOnHardware(options = {}) {
        return this.request('/display', {
            method: 'POST',
            body: JSON.stringify(options)
        });
    },

    async clearDisplay(color = 255) {
        return this.request('/clear-display', {
            method: 'POST',
            body: JSON.stringify({ color })
        });
    },

    async getHardwareStatus() {
        return this.request('/hardware-status');
    },

    // Templates
    async getTemplates() {
        return this.request('/templates');
    },

    async saveTemplate(name, description = '') {
        return this.request('/templates', {
            method: 'POST',
            body: JSON.stringify({ name, description })
        });
    },

    async loadTemplate(name) {
        return this.request(`/templates/${name}`);
    },

    async deleteTemplate(name) {
        return this.request(`/templates/${name}`, {
            method: 'DELETE'
        });
    }
};