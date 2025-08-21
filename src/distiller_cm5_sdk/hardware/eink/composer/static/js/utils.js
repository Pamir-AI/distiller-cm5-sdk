/**
 * Utility functions for the E-ink Composer
 */

const Utils = {
    /**
     * Generate a unique ID
     */
    generateId() {
        return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    },

    /**
     * Debounce function to limit rapid calls
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Clamp a value between min and max
     */
    clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    },

    /**
     * Snap value to grid
     */
    snapToGrid(value, gridSize) {
        return Math.round(value / gridSize) * gridSize;
    },

    /**
     * Convert hex color to grayscale value (0-255)
     */
    hexToGrayscale(hex) {
        const r = parseInt(hex.substr(1, 2), 16);
        const g = parseInt(hex.substr(3, 2), 16);
        const b = parseInt(hex.substr(5, 2), 16);
        return Math.round(0.299 * r + 0.587 * g + 0.114 * b);
    },

    /**
     * Convert grayscale value to hex
     */
    grayscaleToHex(value) {
        const hex = value.toString(16).padStart(2, '0');
        return `#${hex}${hex}${hex}`;
    },

    /**
     * Format file size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    },

    /**
     * Load an image and return as Image object
     */
    loadImage(src) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = src;
        });
    },

    /**
     * Convert File to base64
     */
    fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    },

    /**
     * Download data as file
     */
    downloadFile(data, filename, type = 'application/json') {
        const blob = new Blob([data], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    },

    /**
     * Show notification with visual feedback
     */
    showNotification(message, type = 'info', duration = 3000) {
        console.log(`[${type.toUpperCase()}] ${message}`);
        
        // Check for existing notifications and adjust position
        const existingNotifications = document.querySelectorAll('.notification');
        const bottomOffset = 20 + (existingNotifications.length * 70);
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        
        // Add icon based on type
        const icons = {
            error: '❌',
            success: '✅',
            warning: '⚠️',
            info: 'ℹ️'
        };
        
        notification.innerHTML = `
            <span style="margin-right: 8px;">${icons[type] || ''}</span>
            <span>${message}</span>
        `;
        
        notification.style.cssText = `
            position: fixed;
            bottom: ${bottomOffset}px;
            right: 20px;
            padding: 12px 20px;
            background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
            color: white;
            border-radius: 6px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            z-index: 10000;
            animation: ${type === 'error' ? 'slideInRight 0.3s ease, shake 0.5s ease 0.3s' : 'slideInRight 0.3s ease'};
            font-size: 14px;
            max-width: 400px;
            display: flex;
            align-items: center;
            cursor: pointer;
            transition: transform 0.2s;
        `;
        
        // Add hover effect
        notification.onmouseenter = () => {
            notification.style.transform = 'scale(1.02)';
        };
        notification.onmouseleave = () => {
            notification.style.transform = 'scale(1)';
        };
        
        // Click to dismiss immediately
        notification.onclick = () => {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        };
        
        document.body.appendChild(notification);
        
        // Auto remove after specified duration (longer for errors)
        const autoRemoveTime = type === 'error' ? Math.max(duration, 5000) : duration;
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }
        }, autoRemoveTime);
    },

    /**
     * Get mouse position relative to element
     */
    getMousePos(canvas, evt) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: evt.clientX - rect.left,
            y: evt.clientY - rect.top
        };
    },

    /**
     * Check if point is inside rectangle
     */
    pointInRect(x, y, rect) {
        return x >= rect.x && x <= rect.x + rect.width &&
               y >= rect.y && y <= rect.y + rect.height;
    },

    /**
     * Get bounding box of multiple rectangles
     */
    getBoundingBox(rects) {
        if (!rects || rects.length === 0) return null;
        
        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;
        
        for (const rect of rects) {
            minX = Math.min(minX, rect.x);
            minY = Math.min(minY, rect.y);
            maxX = Math.max(maxX, rect.x + rect.width);
            maxY = Math.max(maxY, rect.y + rect.height);
        }
        
        return {
            x: minX,
            y: minY,
            width: maxX - minX,
            height: maxY - minY
        };
    },

    /**
     * Validate position is within canvas bounds
     */
    validatePosition(x, y, width = 0, height = 0, canvasWidth = 250, canvasHeight = 128) {
        const errors = [];
        
        if (x < 0) errors.push(`X position (${x}) cannot be negative`);
        if (y < 0) errors.push(`Y position (${y}) cannot be negative`);
        if (x + width > canvasWidth) errors.push(`Element exceeds right boundary (${x + width} > ${canvasWidth})`);
        if (y + height > canvasHeight) errors.push(`Element exceeds bottom boundary (${y + height} > ${canvasHeight})`);
        
        return {
            valid: errors.length === 0,
            errors: errors
        };
    },

    /**
     * Constrain position to canvas bounds
     */
    constrainToCanvas(x, y, width = 0, height = 0, canvasWidth = 250, canvasHeight = 128) {
        return {
            x: Math.max(0, Math.min(x, canvasWidth - width)),
            y: Math.max(0, Math.min(y, canvasHeight - height))
        };
    },

    /**
     * Validate image file
     */
    validateImageFile(file) {
        const errors = [];
        const maxSize = 10 * 1024 * 1024; // 10MB
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp'];
        
        if (!file) {
            errors.push('No file selected');
        } else {
            if (file.size > maxSize) {
                errors.push(`File too large (${this.formatFileSize(file.size)} > 10MB)`);
            }
            
            if (!allowedTypes.includes(file.type)) {
                errors.push(`Invalid file type: ${file.type}. Allowed: JPEG, PNG, GIF, BMP`);
            }
        }
        
        return {
            valid: errors.length === 0,
            errors: errors
        };
    },

    /**
     * Retry failed operation with exponential backoff
     */
    async retryOperation(operation, maxRetries = 3, initialDelay = 1000) {
        let lastError;
        
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                return await operation();
            } catch (error) {
                lastError = error;
                console.warn(`Attempt ${attempt} failed:`, error);
                
                if (attempt < maxRetries) {
                    const delay = initialDelay * Math.pow(2, attempt - 1);
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
            }
        }
        
        throw lastError;
    }
};