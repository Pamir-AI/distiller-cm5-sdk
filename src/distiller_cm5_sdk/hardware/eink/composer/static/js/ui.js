/**
 * UI management for the E-ink Composer
 */

const UI = {
    init() {
        this.setupLayerPanel();
        this.setupPropertyPanel();
        this.setupActions();
        this.setupModals();
        this.subscribeToState();
    },
    
    subscribeToState() {
        state.subscribe('layersChanged', (layers) => this.updateLayerList(layers));
        state.subscribe('selectionChanged', (layer) => this.updatePropertyPanel(layer));
        state.subscribe('toolChanged', (tool) => this.updateToolUI(tool));
        state.subscribe('historyChanged', ({ canUndo, canRedo }) => {
            document.getElementById('undoBtn').disabled = !canUndo;
            document.getElementById('redoBtn').disabled = !canRedo;
        });
        state.subscribe('canvasSizeChanged', ({ width, height }) => {
            document.getElementById('canvasSize').textContent = `${width}×${height}`;
        });
    },
    
    setupLayerPanel() {
        // Add layer button
        document.getElementById('addLayerBtn').addEventListener('click', () => {
            this.showAddLayerMenu();
        });
    },
    
    updateLayerList(layers) {
        const layerList = document.getElementById('layerList');
        layerList.innerHTML = '';
        
        // Add layers in reverse order (top to bottom)
        [...layers].reverse().forEach((layer, index) => {
            const layerItem = this.createLayerItem(layer);
            layerList.appendChild(layerItem);
        });
    },
    
    createLayerItem(layer) {
        const div = document.createElement('div');
        div.className = 'layer-item';
        div.dataset.layerId = layer.id;
        
        if (layer.id === state.selectedLayerId) {
            div.classList.add('selected');
        }
        
        if (!layer.visible) {
            div.classList.add('hidden');
        }
        
        // Layer icon
        const icon = document.createElement('div');
        icon.className = 'layer-icon';
        icon.innerHTML = this.getLayerIcon(layer.type);
        
        // Layer name
        const name = document.createElement('div');
        name.className = 'layer-name';
        name.textContent = this.getLayerName(layer);
        
        // Layer actions
        const actions = document.createElement('div');
        actions.className = 'layer-actions';
        
        // Visibility toggle
        const visBtn = document.createElement('button');
        visBtn.className = 'icon-btn';
        visBtn.innerHTML = layer.visible ? '👁' : '👁‍🗨';
        visBtn.onclick = (e) => {
            e.stopPropagation();
            state.toggleLayerVisibility(layer.id);
            API.toggleLayer(layer.id).catch(console.error);
        };
        
        // Delete button
        const delBtn = document.createElement('button');
        delBtn.className = 'icon-btn';
        delBtn.innerHTML = '🗑';
        delBtn.onclick = (e) => {
            e.stopPropagation();
            if (confirm('Delete this layer?')) {
                state.removeLayer(layer.id);
                API.deleteLayer(layer.id).catch(console.error);
            }
        };
        
        actions.appendChild(visBtn);
        actions.appendChild(delBtn);
        
        div.appendChild(icon);
        div.appendChild(name);
        div.appendChild(actions);
        
        // Click to select
        div.onclick = () => {
            state.selectLayer(layer.id);
        };
        
        return div;
    },
    
    getLayerIcon(type) {
        const icons = {
            text: 'T',
            rectangle: '▭',
            image: '🖼',
            placeholder: '⚡'
        };
        return icons[type] || '?';
    },
    
    getLayerName(layer) {
        if (layer.type === 'text') {
            return layer.text || 'Empty Text';
        } else if (layer.type === 'rectangle') {
            return `Rectangle ${layer.width}×${layer.height}`;
        } else if (layer.type === 'image') {
            return 'Image';
        } else if (layer.type === 'placeholder') {
            return layer.placeholderType === 'ip' ? 'IP Address' : 'QR Code';
        }
        return layer.type;
    },
    
    showAddLayerMenu() {
        // Create a dropdown menu instead of using prompt
        const button = document.getElementById('addLayerBtn');
        const rect = button.getBoundingClientRect();
        
        // Create dropdown if it doesn't exist
        let dropdown = document.getElementById('layerDropdown');
        if (!dropdown) {
            dropdown = document.createElement('div');
            dropdown.id = 'layerDropdown';
            dropdown.className = 'dropdown-menu';
            dropdown.innerHTML = `
                <div class="dropdown-item" data-tool="text">
                    <span class="dropdown-icon">T</span> Text
                </div>
                <div class="dropdown-item" data-tool="rectangle">
                    <span class="dropdown-icon">▭</span> Rectangle
                </div>
                <div class="dropdown-item" data-tool="image">
                    <span class="dropdown-icon">🖼</span> Image
                </div>
                <div class="dropdown-divider"></div>
                <div class="dropdown-item" data-tool="ip">
                    <span class="dropdown-icon">IP</span> IP Address
                </div>
                <div class="dropdown-item" data-tool="qr">
                    <span class="dropdown-icon">QR</span> QR Code
                </div>
            `;
            document.body.appendChild(dropdown);
            
            // Add click handlers
            dropdown.querySelectorAll('.dropdown-item').forEach(item => {
                item.addEventListener('click', () => {
                    const tool = item.dataset.tool;
                    Tools.setTool(tool);
                    this.hideDropdown();
                });
            });
            
            // Click outside to close
            document.addEventListener('click', (e) => {
                if (!dropdown.contains(e.target) && e.target !== button) {
                    this.hideDropdown();
                }
            });
        }
        
        // Position and show dropdown
        dropdown.style.position = 'absolute';
        dropdown.style.top = `${rect.bottom + 5}px`;
        dropdown.style.left = `${rect.left}px`;
        dropdown.style.display = 'block';
    },
    
    hideDropdown() {
        const dropdown = document.getElementById('layerDropdown');
        if (dropdown) {
            dropdown.style.display = 'none';
        }
    },
    
    setupPropertyPanel() {
        // Property panel will be updated when selection changes
    },
    
    updatePropertyPanel(layer) {
        const content = document.getElementById('propertyContent');
        
        if (!layer) {
            content.innerHTML = '<div class="empty-state"><p>Select a layer to edit its properties</p></div>';
            return;
        }
        
        content.innerHTML = '';
        
        // Basic properties
        const basicGroup = this.createPropertyGroup('Basic Properties');
        
        // Position
        const posRow = document.createElement('div');
        posRow.className = 'property-row';
        
        posRow.appendChild(this.createNumberField('X', layer.x, (value) => {
            layer.x = parseInt(value);
            state.updateLayer(layer.id, { x: layer.x });
            API.updateLayer(layer.id, { x: layer.x }).catch(console.error);
            canvasManager.render();
        }));
        
        posRow.appendChild(this.createNumberField('Y', layer.y, (value) => {
            layer.y = parseInt(value);
            state.updateLayer(layer.id, { y: layer.y });
            API.updateLayer(layer.id, { y: layer.y }).catch(console.error);
            canvasManager.render();
        }));
        
        basicGroup.appendChild(posRow);
        
        // Type-specific properties
        if (layer.type === 'text') {
            basicGroup.appendChild(this.createTextField('Text', layer.text, (value) => {
                layer.text = value;
                state.updateLayer(layer.id, { text: value });
                API.updateLayer(layer.id, { text: value }).catch(console.error);
                canvasManager.render();
            }));
            
            basicGroup.appendChild(this.createRangeField('Font Size', layer.fontSize, 1, 5, (value) => {
                layer.fontSize = parseInt(value);
                state.updateLayer(layer.id, { font_size: layer.fontSize });
                API.updateLayer(layer.id, { font_size: layer.fontSize }).catch(console.error);
                canvasManager.render();
            }));
            
            basicGroup.appendChild(this.createRangeField('Color', layer.color, 0, 255, (value) => {
                layer.color = parseInt(value);
                state.updateLayer(layer.id, { color: layer.color });
                API.updateLayer(layer.id, { color: layer.color }).catch(console.error);
                canvasManager.render();
            }));
            
            basicGroup.appendChild(this.createCheckboxField('Background', layer.background, (value) => {
                layer.background = value;
                state.updateLayer(layer.id, { background: value });
                API.updateLayer(layer.id, { background: value }).catch(console.error);
                canvasManager.render();
            }));
        } else if (layer.type === 'rectangle') {
            const sizeRow = document.createElement('div');
            sizeRow.className = 'property-row';
            
            sizeRow.appendChild(this.createNumberField('Width', layer.width, (value) => {
                layer.width = parseInt(value);
                state.updateLayer(layer.id, { width: layer.width });
                API.updateLayer(layer.id, { width: layer.width }).catch(console.error);
                canvasManager.render();
            }));
            
            sizeRow.appendChild(this.createNumberField('Height', layer.height, (value) => {
                layer.height = parseInt(value);
                state.updateLayer(layer.id, { height: layer.height });
                API.updateLayer(layer.id, { height: layer.height }).catch(console.error);
                canvasManager.render();
            }));
            
            basicGroup.appendChild(sizeRow);
            
            basicGroup.appendChild(this.createCheckboxField('Filled', layer.filled, (value) => {
                layer.filled = value;
                state.updateLayer(layer.id, { filled: value });
                API.updateLayer(layer.id, { filled: value }).catch(console.error);
                canvasManager.render();
            }));
            
            basicGroup.appendChild(this.createRangeField('Color', layer.color, 0, 255, (value) => {
                layer.color = parseInt(value);
                state.updateLayer(layer.id, { color: layer.color });
                API.updateLayer(layer.id, { color: layer.color }).catch(console.error);
                canvasManager.render();
            }));
        }
        
        content.appendChild(basicGroup);
    },
    
    createPropertyGroup(title) {
        const group = document.createElement('div');
        group.className = 'property-group';
        
        const header = document.createElement('h3');
        header.textContent = title;
        group.appendChild(header);
        
        return group;
    },
    
    createTextField(label, value, onChange) {
        const field = document.createElement('div');
        field.className = 'property-field';
        
        const labelEl = document.createElement('label');
        labelEl.textContent = label;
        field.appendChild(labelEl);
        
        const input = document.createElement('input');
        input.type = 'text';
        input.value = value || '';
        input.addEventListener('change', (e) => onChange(e.target.value));
        field.appendChild(input);
        
        return field;
    },
    
    createNumberField(label, value, onChange) {
        const field = document.createElement('div');
        field.className = 'property-field';
        
        const labelEl = document.createElement('label');
        labelEl.textContent = label;
        field.appendChild(labelEl);
        
        const input = document.createElement('input');
        input.type = 'number';
        input.value = value || 0;
        input.addEventListener('change', (e) => onChange(e.target.value));
        field.appendChild(input);
        
        return field;
    },
    
    createRangeField(label, value, min, max, onChange) {
        const field = document.createElement('div');
        field.className = 'property-field';
        
        const labelEl = document.createElement('label');
        labelEl.textContent = `${label}: ${value}`;
        field.appendChild(labelEl);
        
        const input = document.createElement('input');
        input.type = 'range';
        input.min = min;
        input.max = max;
        input.value = value || min;
        input.addEventListener('input', (e) => {
            labelEl.textContent = `${label}: ${e.target.value}`;
            onChange(e.target.value);
        });
        field.appendChild(input);
        
        return field;
    },
    
    createCheckboxField(label, value, onChange) {
        const field = document.createElement('div');
        field.className = 'property-field';
        
        const labelEl = document.createElement('label');
        labelEl.style.display = 'flex';
        labelEl.style.alignItems = 'center';
        labelEl.style.gap = '8px';
        
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = value || false;
        input.addEventListener('change', (e) => onChange(e.target.checked));
        
        labelEl.appendChild(input);
        labelEl.appendChild(document.createTextNode(label));
        field.appendChild(labelEl);
        
        return field;
    },
    
    setupActions() {
        // Grid toggle
        document.getElementById('gridToggle').addEventListener('change', (e) => {
            state.toggleGrid();
        });
        
        // Snap toggle
        document.getElementById('snapToggle').addEventListener('change', (e) => {
            state.toggleSnap();
        });
        
        // Undo/Redo
        document.getElementById('undoBtn').addEventListener('click', () => state.undo());
        document.getElementById('redoBtn').addEventListener('click', () => state.redo());
        
        // Clear layers
        document.getElementById('clearLayersBtn').addEventListener('click', () => {
            if (confirm('Clear all layers from composer?')) {
                state.clearLayers();
                API.clearAllLayers().then(() => {
                    canvasManager.render();
                    Utils.showNotification('Layers cleared', 'success');
                }).catch(console.error);
            }
        });
        
        // Clear display
        document.getElementById('clearDisplayBtn').addEventListener('click', async () => {
            if (confirm('Clear the e-ink display to white?')) {
                try {
                    const response = await API.clearDisplay(255); // 255 = white
                    if (response.success) {
                        Utils.showNotification('Display cleared', 'success');
                    } else {
                        Utils.showNotification(response.error || 'Failed to clear display', 'error');
                    }
                } catch (error) {
                    Utils.showNotification('Clear display error: ' + error.message, 'error');
                }
            }
        });
        
        // Save template
        document.getElementById('saveBtn').addEventListener('click', () => {
            this.showSaveTemplateDialog();
        });
        
        // Load template
        document.getElementById('loadBtn').addEventListener('click', () => {
            this.showLoadTemplateDialog();
        });
        
        // Display on hardware
        document.getElementById('displayBtn').addEventListener('click', async () => {
            try {
                const response = await API.displayOnHardware();
                if (response.success) {
                    Utils.showNotification('Displayed on e-ink', 'success');
                } else {
                    Utils.showNotification(response.error || 'Display failed', 'error');
                }
            } catch (error) {
                Utils.showNotification('Display error: ' + error.message, 'error');
            }
        });
    },
    
    setupModals() {
        const modal = document.getElementById('templateModal');
        const closeBtn = document.getElementById('closeModalBtn');
        
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('show');
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('show');
            }
        });
    },
    
    showSaveTemplateDialog() {
        const modal = document.getElementById('templateModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBody');
        
        modalTitle.textContent = 'Save Template';
        modalBody.innerHTML = `
            <div class="modal-form">
                <div class="form-group">
                    <label for="templateName">Template Name</label>
                    <input type="text" id="templateName" placeholder="Enter template name" autofocus>
                </div>
                <div class="form-group">
                    <label for="templateDesc">Description (Optional)</label>
                    <textarea id="templateDesc" placeholder="Enter description" rows="3"></textarea>
                </div>
                <div class="modal-actions">
                    <button class="action-btn" id="cancelSaveBtn">Cancel</button>
                    <button class="action-btn primary" id="confirmSaveBtn">Save</button>
                </div>
            </div>
        `;
        
        modal.style.display = 'block';
        
        // Focus on name input
        setTimeout(() => {
            document.getElementById('templateName').focus();
        }, 100);
        
        // Handle save
        document.getElementById('confirmSaveBtn').onclick = async () => {
            const name = document.getElementById('templateName').value.trim();
            const description = document.getElementById('templateDesc').value.trim();
            
            if (!name) {
                Utils.showNotification('Please enter a template name', 'warning');
                return;
            }
            
            try {
                const response = await API.saveTemplate(name, description);
                if (response.success) {
                    Utils.showNotification('Template saved successfully', 'success');
                    modal.style.display = 'none';
                }
            } catch (error) {
                Utils.showNotification('Failed to save template', 'error');
            }
        };
        
        // Handle cancel
        document.getElementById('cancelSaveBtn').onclick = () => {
            modal.style.display = 'none';
        };
    },
    
    async showLoadTemplateDialog() {
        try {
            const response = await API.getTemplates();
            const templates = response.templates || [];
            
            const modal = document.getElementById('templateModal');
            const modalTitle = document.getElementById('modalTitle');
            const modalBody = document.getElementById('modalBody');
            
            modalTitle.textContent = 'Load Template';
            modalBody.innerHTML = '';
            
            if (templates.length === 0) {
                modalBody.innerHTML = '<div class="empty-state"><p>No templates found</p></div>';
            } else {
                const list = document.createElement('div');
                list.className = 'template-list';
                
                templates.forEach(template => {
                    const item = document.createElement('div');
                    item.className = 'template-item';
                    item.onclick = () => {
                        this.loadTemplate(template.name);
                        modal.classList.remove('show');
                    };
                    
                    const info = document.createElement('div');
                    info.className = 'template-info';
                    
                    const name = document.createElement('div');
                    name.className = 'template-name';
                    name.textContent = template.name;
                    
                    const meta = document.createElement('div');
                    meta.className = 'template-meta';
                    meta.textContent = `${template.layers_count} layers • ${template.width}×${template.height}`;
                    
                    info.appendChild(name);
                    info.appendChild(meta);
                    item.appendChild(info);
                    list.appendChild(item);
                });
                
                modalBody.appendChild(list);
            }
            
            modal.classList.add('show');
        } catch (error) {
            Utils.showNotification('Failed to load templates', 'error');
        }
    },
    
    async loadTemplate(name) {
        try {
            const response = await API.loadTemplate(name);
            if (response.success) {
                // Template loaded on server, now reload layers
                await canvasManager.loadLayersFromServer();
                Utils.showNotification('Template loaded', 'success');
            }
        } catch (error) {
            Utils.showNotification('Failed to load template', 'error');
        }
    },
    
    updateToolUI(tool) {
        // Update cursor style based on tool
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
            default:
                canvas.style.cursor = 'default';
        }
    }
};