/**
 * Layer classes for the E-ink Composer
 */

class Layer {
    constructor(id, type, x = 0, y = 0) {
        // For real layers, ID should be provided by server
        // Only temp layers should generate local IDs
        if (!id) {
            console.warn(`Creating ${type} layer without server ID - this should only be for temporary layers`);
            this.id = `temp_${Utils.generateId()}`;
        } else {
            this.id = id;
        }
        this.type = type;
        this.x = x;
        this.y = y;
        this.visible = true;
        this.locked = false;
    }

    /**
     * Draw the layer on canvas (to be overridden)
     */
    draw(ctx) {
        // Override in subclasses
    }

    /**
     * Get bounding box
     */
    getBounds() {
        return {
            x: this.x,
            y: this.y,
            width: 0,
            height: 0
        };
    }

    /**
     * Check if point is inside layer
     */
    hitTest(x, y) {
        const bounds = this.getBounds();
        return Utils.pointInRect(x, y, bounds);
    }

    /**
     * Move layer
     */
    move(dx, dy) {
        this.x += dx;
        this.y += dy;
    }

    /**
     * Set position
     */
    setPosition(x, y) {
        this.x = x;
        this.y = y;
    }

    /**
     * Clone the layer
     */
    clone() {
        return Object.assign(Object.create(Object.getPrototypeOf(this)), this);
    }
}

class TextLayer extends Layer {
    constructor(id, text = '', x = 0, y = 0) {
        super(id, 'text', x, y);
        this.text = text;
        this.color = 0; // 0 = black, 255 = white
        this.fontSize = 1;
        this.background = false;
        this.padding = 2;
        this.font = '12px monospace';
    }

    draw(ctx) {
        if (!this.visible || !this.text) return;

        ctx.save();
        
        // Set font
        const actualFontSize = 12 * this.fontSize;
        ctx.font = `${actualFontSize}px monospace`;
        
        // Measure text
        const metrics = ctx.measureText(this.text);
        const textWidth = metrics.width;
        const textHeight = actualFontSize;
        
        // Draw background if enabled
        if (this.background) {
            ctx.fillStyle = 'white';
            ctx.fillRect(
                this.x - this.padding,
                this.y - this.padding,
                textWidth + this.padding * 2,
                textHeight + this.padding * 2
            );
        }
        
        // Draw text (binary colors only: 0=black, 255=white)
        ctx.fillStyle = this.color === 0 ? 'black' : 'white';
        ctx.textBaseline = 'top';
        ctx.fillText(this.text, this.x, this.y);
        
        ctx.restore();
    }

    getBounds() {
        // Estimate bounds based on text length and font size
        const charWidth = 7 * this.fontSize;
        const charHeight = 12 * this.fontSize;
        const width = this.text.length * charWidth;
        const height = charHeight;
        
        return {
            x: this.x - (this.background ? this.padding : 0),
            y: this.y - (this.background ? this.padding : 0),
            width: width + (this.background ? this.padding * 2 : 0),
            height: height + (this.background ? this.padding * 2 : 0)
        };
    }
}

class RectangleLayer extends Layer {
    constructor(id, x = 0, y = 0, width = 50, height = 30) {
        super(id, 'rectangle', x, y);
        this.width = width;
        this.height = height;
        this.filled = true;
        this.color = 0; // 0 = black, 255 = white
        this.borderWidth = 1;
    }

    draw(ctx) {
        if (!this.visible) return;

        ctx.save();
        
        // Binary colors only: 0=black, 255=white
        const colorStr = this.color === 0 ? 'black' : 'white';
        
        if (this.filled) {
            ctx.fillStyle = colorStr;
            ctx.fillRect(this.x, this.y, this.width, this.height);
        } else {
            ctx.strokeStyle = colorStr;
            ctx.lineWidth = this.borderWidth;
            ctx.strokeRect(this.x, this.y, this.width, this.height);
        }
        
        ctx.restore();
    }

    getBounds() {
        return {
            x: this.x,
            y: this.y,
            width: this.width,
            height: this.height
        };
    }

    /**
     * Resize the rectangle
     */
    resize(width, height) {
        this.width = Math.max(1, width);
        this.height = Math.max(1, height);
    }
}

class ImageLayer extends Layer {
    constructor(id, imageSrc = null, x = 0, y = 0) {
        super(id, 'image', x, y);
        this.imageSrc = imageSrc;
        this.imageElement = null;
        this.width = null;
        this.height = null;
        this.originalWidth = null;
        this.originalHeight = null;
        this.resizeMode = 'fit'; // 'fit', 'stretch', 'crop'
        this.ditherMode = 'floyd-steinberg';
        
        if (imageSrc) {
            this.loadImage(imageSrc);
        }
    }

    async loadImage(src) {
        try {
            this.imageElement = await Utils.loadImage(src);
            this.originalWidth = this.imageElement.width;
            this.originalHeight = this.imageElement.height;
            
            // Set default size if not specified
            if (!this.width) this.width = this.originalWidth;
            if (!this.height) this.height = this.originalHeight;
        } catch (error) {
            console.error('Failed to load image:', error);
        }
    }

    draw(ctx) {
        if (!this.visible || !this.imageElement) return;

        ctx.save();
        
        // Apply dithering by converting to grayscale
        // Note: Full dithering would require pixel manipulation
        ctx.filter = 'grayscale(100%)';
        
        if (this.resizeMode === 'stretch') {
            ctx.drawImage(this.imageElement, this.x, this.y, this.width, this.height);
        } else if (this.resizeMode === 'fit') {
            const scale = Math.min(
                this.width / this.originalWidth,
                this.height / this.originalHeight
            );
            const newWidth = this.originalWidth * scale;
            const newHeight = this.originalHeight * scale;
            const offsetX = (this.width - newWidth) / 2;
            const offsetY = (this.height - newHeight) / 2;
            
            ctx.drawImage(
                this.imageElement,
                this.x + offsetX,
                this.y + offsetY,
                newWidth,
                newHeight
            );
        } else if (this.resizeMode === 'crop') {
            // Center crop
            const scale = Math.max(
                this.width / this.originalWidth,
                this.height / this.originalHeight
            );
            const newWidth = this.originalWidth * scale;
            const newHeight = this.originalHeight * scale;
            const offsetX = (this.width - newWidth) / 2;
            const offsetY = (this.height - newHeight) / 2;
            
            ctx.save();
            ctx.beginPath();
            ctx.rect(this.x, this.y, this.width, this.height);
            ctx.clip();
            
            ctx.drawImage(
                this.imageElement,
                this.x + offsetX,
                this.y + offsetY,
                newWidth,
                newHeight
            );
            ctx.restore();
        } else {
            // Default: draw at original size
            ctx.drawImage(this.imageElement, this.x, this.y);
        }
        
        ctx.restore();
    }

    getBounds() {
        return {
            x: this.x,
            y: this.y,
            width: this.width || this.originalWidth || 0,
            height: this.height || this.originalHeight || 0
        };
    }

    resize(width, height) {
        this.width = Math.max(1, width);
        this.height = Math.max(1, height);
    }
}

class PlaceholderLayer extends Layer {
    constructor(id, type, x = 0, y = 0) {
        super(id, 'placeholder', x, y);
        this.placeholderType = type; // 'ip' or 'qr'
        this.width = type === 'qr' ? 70 : 100;
        this.height = type === 'qr' ? 70 : 20;
        this.data = null;
    }

    draw(ctx) {
        if (!this.visible) return;

        ctx.save();
        
        // Draw placeholder rectangle
        ctx.strokeStyle = '#666';
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(this.x, this.y, this.width, this.height);
        
        // Draw label
        ctx.fillStyle = '#666';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(
            this.placeholderType === 'ip' ? 'IP Address' : 'QR Code',
            this.x + this.width / 2,
            this.y + this.height / 2
        );
        
        ctx.restore();
    }

    getBounds() {
        return {
            x: this.x,
            y: this.y,
            width: this.width,
            height: this.height
        };
    }
}

/**
 * Create layer from server data
 */
function createLayerFromData(data) {
    let layer;
    
    switch (data.type) {
        case 'text':
            layer = new TextLayer(data.id, data.text, data.x, data.y);
            layer.color = data.color || 0;
            layer.fontSize = data.font_size || 1;
            layer.background = data.background || false;
            layer.padding = data.padding || 2;
            break;
            
        case 'rectangle':
            layer = new RectangleLayer(data.id, data.x, data.y, data.width, data.height);
            layer.filled = data.filled !== false;
            layer.color = data.color || 0;
            layer.borderWidth = data.border_width || 1;
            break;
            
        case 'image':
            layer = new ImageLayer(data.id, data.image_path, data.x, data.y);
            layer.width = data.width;
            layer.height = data.height;
            break;
            
        default:
            layer = new Layer(data.id, data.type, data.x, data.y);
    }
    
    layer.visible = data.visible !== false;
    return layer;
}