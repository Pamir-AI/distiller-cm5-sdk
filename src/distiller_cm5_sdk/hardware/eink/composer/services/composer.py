"""Core composer service for managing layers and composition."""

import uuid
from typing import Optional

from ..layers import ImageLayer, Layer, RectangleLayer, TextLayer
from .debug import debug, debug_manager, error, info, log_call, timed_operation


class ComposerService:
    """Service for managing e-ink composition layers."""

    def __init__(self, width: int = 250, height: int = 128):
        """Initialize composer with display dimensions."""
        self.width = width
        self.height = height
        self.layers: dict[str, Layer] = {}
        self.layer_order: list[str] = []
        info(f"ComposerService initialized: {width}x{height}")

    @timed_operation("add_text_layer")
    @log_call
    def add_text_layer(
        self,
        text: str,
        x: int = 0,
        y: int = 0,
        color: int = 0,
        font_size: int = 1,
        background: bool = False,
        padding: int = 2,
    ) -> str:
        """Add a text layer to the composition."""
        layer_id = f"text_{uuid.uuid4().hex[:8]}"
        layer = TextLayer(
            id=layer_id,
            text=text,
            x=x,
            y=y,
            color=color,
            font_size=font_size,
            background=background,
            padding=padding,
        )
        self.layers[layer_id] = layer
        self.layer_order.append(layer_id)
        debug(f"Added text layer: {layer_id} at ({x}, {y}) with text: '{text}'")
        return layer_id

    @timed_operation("add_rectangle_layer")
    @log_call
    def add_rectangle_layer(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 50,
        height: int = 30,
        filled: bool = True,
        color: int = 0,
        border_width: int = 1,
    ) -> str:
        """Add a rectangle layer to the composition."""
        layer_id = f"rect_{uuid.uuid4().hex[:8]}"
        layer = RectangleLayer(
            id=layer_id,
            x=x,
            y=y,
            width=width,
            height=height,
            filled=filled,
            color=color,
            border_width=border_width,
        )
        self.layers[layer_id] = layer
        self.layer_order.append(layer_id)
        debug(f"Added rectangle layer: {layer_id} at ({x}, {y}) size: {width}x{height}")
        return layer_id

    @timed_operation("add_image_layer")
    @log_call
    def add_image_layer(
        self,
        image_path: str,
        x: int = 0,
        y: int = 0,
        width: int | None = None,
        height: int | None = None,
        resize_mode: str = "fit",
        dither_mode: str = "floyd-steinberg",
    ) -> str:
        """Add an image layer to the composition."""
        layer_id = f"img_{uuid.uuid4().hex[:8]}"
        layer = ImageLayer(
            id=layer_id,
            x=x,
            y=y,
            image_path=image_path,
            width=width,
            height=height,
            resize_mode=resize_mode,
            dither_mode=dither_mode,
        )
        self.layers[layer_id] = layer
        self.layer_order.append(layer_id)
        debug(f"Added image layer: {layer_id} at ({x}, {y}) from {image_path}")
        return layer_id

    @log_call
    def update_layer(self, layer_id: str, **kwargs) -> bool:
        """Update layer properties."""
        if layer_id not in self.layers:
            debug(f"Layer not found for update: {layer_id}")
            return False

        layer = self.layers[layer_id]
        debug(f"Updating layer {layer_id} with: {kwargs}")
        for key, value in kwargs.items():
            if hasattr(layer, key):
                setattr(layer, key, value)
        return True

    @log_call
    def remove_layer(self, layer_id: str) -> bool:
        """Remove a layer from the composition."""
        if layer_id not in self.layers:
            debug(f"Layer not found for removal: {layer_id}")
            return False

        del self.layers[layer_id]
        self.layer_order.remove(layer_id)
        info(f"Removed layer: {layer_id}")
        return True

    def toggle_layer(self, layer_id: str) -> bool:
        """Toggle layer visibility."""
        if layer_id not in self.layers:
            return False

        layer = self.layers[layer_id]
        layer.visible = not layer.visible
        return True

    def reorder_layer(self, layer_id: str, new_index: int) -> bool:
        """Change layer order."""
        if layer_id not in self.layers:
            return False

        if not 0 <= new_index < len(self.layer_order):
            return False

        self.layer_order.remove(layer_id)
        self.layer_order.insert(new_index, layer_id)
        return True

    def get_layer(self, layer_id: str) -> Layer | None:
        """Get a specific layer."""
        return self.layers.get(layer_id)

    def get_layers(self) -> list[Layer]:
        """Get all layers in order."""
        return [self.layers[lid] for lid in self.layer_order if lid in self.layers]

    def get_visible_layers(self) -> list[Layer]:
        """Get only visible layers in order."""
        return [
            self.layers[lid]
            for lid in self.layer_order
            if lid in self.layers and self.layers[lid].visible
        ]

    def clear(self):
        """Clear all layers."""
        layer_count = len(self.layers)
        self.layers.clear()
        self.layer_order.clear()
        info(f"Cleared {layer_count} layers")

    @timed_operation("export_composition")
    def to_dict(self) -> dict:
        """Export composition as dictionary."""
        debug(f"Exporting composition with {len(self.layers)} layers")
        return {
            "width": self.width,
            "height": self.height,
            "layers": [
                {
                    "id": layer.id,
                    "type": layer.type,
                    "visible": layer.visible,
                    "x": layer.x,
                    "y": layer.y,
                    **{
                        k: v
                        for k, v in layer.__dict__.items()
                        if k not in ["id", "type", "visible", "x", "y", "image_data"]
                    },
                }
                for layer in self.get_layers()
            ],
        }

    @timed_operation("import_composition")
    def from_dict(self, data: dict):
        """Import composition from dictionary."""
        self.clear()
        self.width = data.get("width", 250)
        self.height = data.get("height", 128)
        info(
            f"Importing composition: {self.width}x{self.height} with {len(data.get('layers', []))} layers"
        )

        for layer_data in data.get("layers", []):
            layer_type = layer_data.get("type")
            if layer_type == "text":
                self.add_text_layer(
                    text=layer_data.get("text", ""),
                    x=layer_data.get("x", 0),
                    y=layer_data.get("y", 0),
                    color=layer_data.get("color", 0),
                    font_size=layer_data.get("font_size", 1),
                    background=layer_data.get("background", False),
                    padding=layer_data.get("padding", 2),
                )
            elif layer_type == "rectangle":
                self.add_rectangle_layer(
                    x=layer_data.get("x", 0),
                    y=layer_data.get("y", 0),
                    width=layer_data.get("width", 50),
                    height=layer_data.get("height", 30),
                    filled=layer_data.get("filled", True),
                    color=layer_data.get("color", 0),
                    border_width=layer_data.get("border_width", 1),
                )
            elif layer_type == "image" and "image_path" in layer_data:
                self.add_image_layer(
                    image_path=layer_data["image_path"],
                    x=layer_data.get("x", 0),
                    y=layer_data.get("y", 0),
                    width=layer_data.get("width"),
                    height=layer_data.get("height"),
                    resize_mode=layer_data.get("resize_mode", "fit"),
                    dither_mode=layer_data.get("dither_mode", "floyd-steinberg"),
                )
