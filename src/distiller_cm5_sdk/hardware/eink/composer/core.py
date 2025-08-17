"""E-ink composer core."""

import json
import os
import tempfile
from pathlib import Path
from typing import Literal, Optional, Union

import numpy as np
from PIL import Image

from .. import Display, DisplayMode, DitheringMethod, ScalingMethod
from .layers import ImageLayer, Layer, RectangleLayer, TextLayer
from .text import measure_text, render_text


class EinkComposer:
    def __init__(self, width: int = 128, height: int = 250):
        self.width = width
        self.height = height
        self.layers: list[Layer] = []
        self.canvas = np.full((height, width), 255, dtype=np.uint8)
        self._display: Display | None = None

    def _get_display(self) -> Display:
        if self._display is None:
            self._display = Display(auto_init=False)
        return self._display

    def add_image_layer(
        self,
        layer_id: str,
        image_path: str,
        x: int = 0,
        y: int = 0,
        resize_mode: Literal["stretch", "fit", "crop"] = "fit",
        dither_mode: Literal["floyd-steinberg", "threshold", "none"] = "floyd-steinberg",
        brightness: float = 1.0,
        contrast: float = 0.0,
        rotate: int = 0,
        flip_h: bool = False,
        flip_v: bool = False,
        crop_x: int | None = None,
        crop_y: int | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> str:
        layer = ImageLayer(
            id=layer_id,
            image_path=image_path,
            x=x,
            y=y,
            resize_mode=resize_mode,
            dither_mode=dither_mode,
            brightness=brightness,
            contrast=contrast,
            rotate=rotate,
            flip_h=flip_h,
            flip_v=flip_v,
            crop_x=crop_x,
            crop_y=crop_y,
            width=width,
            height=height,
        )
        self.layers.append(layer)
        return layer_id

    def add_text_layer(
        self,
        layer_id: str,
        text: str,
        x: int = 0,
        y: int = 0,
        color: int = 0,
        font_size: int = 1,
        rotate: int = 0,
        flip_h: bool = False,
        flip_v: bool = False,
        background: bool = False,
        padding: int = 2,
    ) -> str:
        layer = TextLayer(
            id=layer_id,
            text=text,
            x=x,
            y=y,
            color=color,
            font_size=font_size,
            rotate=rotate,
            flip_h=flip_h,
            flip_v=flip_v,
            background=background,
            padding=padding,
        )
        self.layers.append(layer)
        return layer_id

    def add_rectangle_layer(
        self,
        layer_id: str,
        x: int = 0,
        y: int = 0,
        width: int = 10,
        height: int = 10,
        filled: bool = True,
        color: int = 0,
        border_width: int = 1,
    ) -> str:
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
        self.layers.append(layer)
        return layer_id

    def remove_layer(self, layer_id: str) -> bool:
        for i, layer in enumerate(self.layers):
            if layer.id == layer_id:
                del self.layers[i]
                return True
        return False

    def update_layer(self, layer_id: str, **kwargs) -> bool:
        for layer in self.layers:
            if layer.id == layer_id:
                for key, value in kwargs.items():
                    if hasattr(layer, key):
                        setattr(layer, key, value)
                return True
        return False

    def toggle_layer(self, layer_id: str) -> bool:
        for layer in self.layers:
            if layer.id == layer_id:
                layer.visible = not layer.visible
                return True
        return False

    def get_layer_info(self) -> list[dict]:
        info = []
        for layer in self.layers:
            layer_dict = {
                "id": layer.id,
                "type": layer.type,
                "visible": layer.visible,
                "x": layer.x,
                "y": layer.y,
            }

            if isinstance(layer, TextLayer):
                layer_dict["text"] = layer.text
                layer_dict["font_size"] = layer.font_size
            elif isinstance(layer, ImageLayer):
                layer_dict["image_path"] = layer.image_path
                layer_dict["resize_mode"] = layer.resize_mode
            elif isinstance(layer, RectangleLayer):
                layer_dict["width"] = layer.width
                layer_dict["height"] = layer.height
                layer_dict["filled"] = layer.filled

            info.append(layer_dict)
        return info

    def _process_text_layer(self, layer: TextLayer, canvas: np.ndarray) -> np.ndarray:
        if not layer.text:
            return canvas

        # Render text to temporary canvas
        text_canvas = render_text(
            layer.text, x=0, y=0, canvas=None, color=layer.color, font_size=layer.font_size
        )

        # Apply transformations
        if layer.rotate != 0:
            text_canvas = np.rot90(text_canvas, k=layer.rotate // 90)
        if layer.flip_h:
            text_canvas = np.fliplr(text_canvas)
        if layer.flip_v:
            text_canvas = np.flipud(text_canvas)

        # Add background if requested
        if layer.background:
            bg_canvas = np.full_like(text_canvas, 255, dtype=np.uint8)
            # Add padding
            if layer.padding > 0:
                padded_h = text_canvas.shape[0] + 2 * layer.padding
                padded_w = text_canvas.shape[1] + 2 * layer.padding
                padded_bg = np.full((padded_h, padded_w), 255, dtype=np.uint8)
                padded_text = np.full((padded_h, padded_w), 255, dtype=np.uint8)
                padded_text[
                    layer.padding : layer.padding + text_canvas.shape[0],
                    layer.padding : layer.padding + text_canvas.shape[1],
                ] = text_canvas
                text_canvas = padded_text
                bg_canvas = padded_bg

            # Composite background
            self._composite_onto_canvas(
                canvas, bg_canvas, layer.x - layer.padding, layer.y - layer.padding
            )

        # Composite text onto canvas
        self._composite_onto_canvas(canvas, text_canvas, layer.x, layer.y)
        return canvas

    def _process_rectangle_layer(self, layer: RectangleLayer, canvas: np.ndarray) -> np.ndarray:
        x1 = max(0, layer.x)
        y1 = max(0, layer.y)
        x2 = min(self.width, layer.x + layer.width)
        y2 = min(self.height, layer.y + layer.height)

        if layer.filled:
            canvas[y1:y2, x1:x2] = layer.color
        else:
            # Draw border
            bw = layer.border_width
            # Top and bottom borders
            canvas[y1 : y1 + bw, x1:x2] = layer.color
            canvas[y2 - bw : y2, x1:x2] = layer.color
            # Left and right borders
            canvas[y1:y2, x1 : x1 + bw] = layer.color
            canvas[y1:y2, x2 - bw : x2] = layer.color

        return canvas

    def _process_image_layer(self, layer: ImageLayer, canvas: np.ndarray) -> np.ndarray:
        if not layer.image_path and layer.image_data is None:
            return canvas

        try:
            if layer.image_path:
                # Use SDK's Rust-based image processing exclusively
                display = self._get_display()

                # Determine target size
                target_width = layer.width if layer.width else self.width - layer.x
                target_height = layer.height if layer.height else self.height - layer.y

                # Map composer resize modes to SDK scaling methods
                scaling = ScalingMethod.LETTERBOX
                if layer.resize_mode == "stretch":
                    scaling = ScalingMethod.STRETCH
                elif layer.resize_mode == "crop":
                    scaling = ScalingMethod.CROP_CENTER
                elif layer.resize_mode == "fit":
                    scaling = ScalingMethod.LETTERBOX

                # Map dithering modes
                dithering = DitheringMethod.FLOYD_STEINBERG
                if layer.dither_mode == "threshold":
                    dithering = DitheringMethod.SIMPLE
                elif layer.dither_mode == "none":
                    dithering = DitheringMethod.SIMPLE  # SDK doesn't have 'none', use simple

                # Create temp file for processed output
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_out:
                    tmp_out_path = tmp_out.name

                try:
                    # Use SDK's display_image_auto for Rust processing
                    # First, we need to process the image to the target size
                    # We'll save it temporarily and use SDK's conversion

                    # The SDK's display_png_auto can handle conversion
                    # We'll use it to process the image with scaling and dithering
                    if not display._initialized:
                        display.initialize()

                    # Use the SDK's image processing by converting through display
                    # Create a temporary composition at target size
                    from PIL import Image

                    # Load original image to get dimensions
                    orig_img = Image.open(layer.image_path)

                    # Apply transformations before SDK processing
                    if layer.flip_h:
                        orig_img = orig_img.transpose(Image.FLIP_LEFT_RIGHT)
                    if layer.flip_v:
                        orig_img = orig_img.transpose(Image.FLIP_TOP_BOTTOM)
                    if layer.rotate != 0:
                        orig_img = orig_img.rotate(-layer.rotate, expand=True)

                    # Save transformed image for SDK processing
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_in:
                        orig_img.save(tmp_in.name)
                        tmp_in_path = tmp_in.name

                    try:
                        # Use SDK's convert_and_process_image method if available
                        # This uses Rust processing internally
                        processed_data = display.convert_and_process_image(
                            tmp_in_path,
                            target_width,
                            target_height,
                            scaling,
                            dithering,
                            crop_x=layer.crop_x,
                            crop_y=layer.crop_y,
                        )

                        if processed_data:
                            # Convert binary data back to numpy array for compositing
                            img_array = np.frombuffer(processed_data, dtype=np.uint8)
                            img_array = img_array.reshape((target_height, target_width))

                            # Composite onto canvas
                            self._composite_onto_canvas(canvas, img_array, layer.x, layer.y)
                        else:
                            print(f"Warning: SDK failed to process image {layer.image_path}")
                    finally:
                        Path(tmp_in_path).unlink(missing_ok=True)

                finally:
                    Path(tmp_out_path).unlink(missing_ok=True)

            elif layer.image_data is not None:
                # Use provided numpy array directly
                self._composite_onto_canvas(canvas, layer.image_data, layer.x, layer.y)

        except Exception as e:
            print(f"Warning: Failed to process image layer {layer.id}: {e}")

        return canvas

    def _composite_onto_canvas(self, canvas: np.ndarray, image: np.ndarray, x: int, y: int) -> None:
        img_h, img_w = image.shape

        # Calculate valid regions
        src_x1 = max(0, -x)
        src_y1 = max(0, -y)
        src_x2 = min(img_w, self.width - x)
        src_y2 = min(img_h, self.height - y)

        dst_x1 = max(0, x)
        dst_y1 = max(0, y)
        dst_x2 = min(self.width, x + img_w)
        dst_y2 = min(self.height, y + img_h)

        # Copy valid region
        if src_x2 > src_x1 and src_y2 > src_y1:
            canvas[dst_y1:dst_y2, dst_x1:dst_x2] = image[src_y1:src_y2, src_x1:src_x2]

    def render(
        self, background_color: int = 255, transformations: list[str] | None = None
    ) -> np.ndarray:
        # Create fresh canvas
        canvas = np.full((self.height, self.width), background_color, dtype=np.uint8)

        # Render layers in order
        for layer in self.layers:
            if not layer.visible:
                continue

            if isinstance(layer, TextLayer):
                canvas = self._process_text_layer(layer, canvas)
            elif isinstance(layer, RectangleLayer):
                canvas = self._process_rectangle_layer(layer, canvas)
            elif isinstance(layer, ImageLayer):
                canvas = self._process_image_layer(layer, canvas)

        # Apply final transformations
        if transformations:
            for transform in transformations:
                if transform == "flip-h":
                    canvas = np.fliplr(canvas)
                elif transform == "flip-v":
                    canvas = np.flipud(canvas)
                elif transform == "rotate-90":
                    canvas = np.rot90(canvas)
                elif transform == "invert":
                    canvas = 255 - canvas

        self.canvas = canvas
        return canvas

    def render_binary(self) -> bytes:
        # Render to array
        img = self.render()

        # Convert to 1-bit (threshold at 128)
        binary = (img > 128).astype(np.uint8)

        # Pack bits (8 pixels per byte, MSB first)
        packed = np.packbits(binary, axis=1)

        return packed.tobytes()

    def save(self, filename: str, format: Literal["png", "bmp", "binary"] = "png") -> None:
        if format == "binary":
            data = self.render_binary()
            with open(filename, "wb") as f:
                f.write(data)
        else:
            img = self.render()
            pil_img = Image.fromarray(img, mode="L")
            pil_img.save(filename)

    def display(
        self,
        mode: DisplayMode = DisplayMode.FULL,
        rotate: bool = False,
        flip_h: bool = False,
        flip_v: bool = False,
    ) -> bool:
        try:
            # Render composition
            img = self.render()

            # Apply display transformations
            if rotate:
                img = np.rot90(img)
            if flip_h:
                img = np.fliplr(img)
            if flip_v:
                img = np.flipud(img)

            # Save to temporary file for SDK display
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                pil_img = Image.fromarray(img, mode="L")
                pil_img.save(tmp.name)
                tmp_path = tmp.name

            # Use SDK's display functionality
            display = self._get_display()
            if not display._initialized:
                display.initialize()

            # Display using SDK's optimized path
            success = display.display_image(tmp_path, mode)

            Path(tmp_path).unlink(missing_ok=True)

            return success

        except Exception as e:
            print(f"Display error: {e}")
            return False

    def clear_display(self) -> bool:
        try:
            display = self._get_display()
            if not display._initialized:
                display.initialize()
            display.clear()
            return True
        except Exception as e:
            print(f"Clear display error: {e}")
            return False

    def to_dict(self) -> dict:
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
                        if k not in ["id", "type", "visible", "x", "y"]
                    },
                }
                for layer in self.layers
            ],
        }

    def from_dict(self, data: dict) -> None:
        self.width = data.get("width", 128)
        self.height = data.get("height", 250)
        self.layers = []

        for layer_data in data.get("layers", []):
            layer_type = layer_data.get("type")
            if layer_type == "text":
                self.add_text_layer(**layer_data)
            elif layer_type == "rectangle":
                self.add_rectangle_layer(**layer_data)
            elif layer_type == "image":
                self.add_image_layer(**layer_data)

    def save_json(self, filename: str) -> None:
        with open(filename, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load_json(self, filename: str) -> None:
        with open(filename) as f:
            data = json.load(f)
        self.from_dict(data)
