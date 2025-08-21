"""Image rendering service for e-ink composer."""

import base64
import io
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..layers import ImageLayer, Layer, RectangleLayer, TextLayer
from .debug import debug, debug_manager, error, info, log_call, timed_operation


class RenderService:
    """Service for rendering layers to images."""

    def __init__(self):
        """Initialize render service."""
        self.font = None
        self._init_font()

    def _init_font(self):
        """Initialize default font."""
        try:
            # Try to use a monospace font
            self.font = ImageFont.load_default()
        except Exception:
            self.font = None

    @timed_operation("render_layers")
    @log_call
    def render_layers(
        self,
        layers: list[Layer],
        width: int = 250,
        height: int = 128,
        background_color: int = 255,
    ) -> Image.Image:
        """Render layers to a PIL Image."""
        debug(f"Rendering {len(layers)} layers to {width}x{height} image")
        # Create base image
        img = Image.new("L", (width, height), background_color)
        draw = ImageDraw.Draw(img)

        # Render each visible layer
        for i, layer in enumerate(layers):
            if not layer.visible:
                debug(f"Skipping invisible layer {i}: {layer.id}")
                continue

            debug(f"Rendering layer {i}: {layer.type} at ({layer.x}, {layer.y})")

            if isinstance(layer, TextLayer):
                self._render_text_layer(img, draw, layer)
            elif isinstance(layer, RectangleLayer):
                self._render_rectangle_layer(draw, layer)
            elif isinstance(layer, ImageLayer):
                self._render_image_layer(img, layer)

        return img

    def _render_text_layer(self, img: Image.Image, draw: ImageDraw.Draw, layer: TextLayer):
        """Render a text layer."""
        # Ensure binary colors (0=black, 255=white)
        text_color = 0 if layer.color == 0 else 255
        
        # Create a temporary image for text with background if needed
        if layer.background:
            # Calculate text size
            bbox = draw.textbbox((0, 0), layer.text, font=self.font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Apply font size scaling
            text_width *= layer.font_size
            text_height *= layer.font_size

            # Draw background rectangle (always white)
            padding = layer.padding
            draw.rectangle(
                [
                    layer.x - padding,
                    layer.y - padding,
                    layer.x + text_width + padding,
                    layer.y + text_height + padding,
                ],
                fill=255,  # White background
            )

        # Draw text
        if layer.font_size == 1:
            draw.text((layer.x, layer.y), layer.text, fill=text_color, font=self.font)
        else:
            # For larger font sizes, scale the text
            # Create temp image with white background
            temp_img = Image.new("L", (img.width, img.height), 255)
            temp_draw = ImageDraw.Draw(temp_img)
            
            # Draw text in the desired color
            temp_draw.text((0, 0), layer.text, fill=text_color, font=self.font)

            # Get bounding box and crop
            bbox = temp_img.getbbox()
            if bbox:
                text_img = temp_img.crop(bbox)
                # Scale
                new_size = (
                    int(text_img.width * layer.font_size),
                    int(text_img.height * layer.font_size),
                )
                text_img = text_img.resize(new_size, Image.Resampling.NEAREST)

                # No color inversion needed - we drew it correctly above
                # Paste onto main image
                img.paste(text_img, (layer.x, layer.y))

    def _render_rectangle_layer(self, draw: ImageDraw.Draw, layer: RectangleLayer):
        """Render a rectangle layer."""
        # Ensure binary colors (0=black, 255=white)
        rect_color = 0 if layer.color == 0 else 255
        
        x1, y1 = layer.x, layer.y
        x2, y2 = layer.x + layer.width, layer.y + layer.height

        if layer.filled:
            draw.rectangle([x1, y1, x2, y2], fill=rect_color)
        else:
            # Draw border
            for i in range(layer.border_width):
                draw.rectangle(
                    [x1 + i, y1 + i, x2 - i, y2 - i],
                    outline=rect_color,
                )

    def _render_image_layer(self, img: Image.Image, layer: ImageLayer):
        """Render an image layer."""
        if not layer.image_path and not layer.image_data:
            return

        try:
            # Load image
            if layer.image_data is not None:
                layer_img = Image.fromarray(layer.image_data)
            else:
                layer_img = Image.open(layer.image_path)

            # Convert to grayscale
            if layer_img.mode != "L":
                layer_img = layer_img.convert("L")

            # Apply brightness and contrast
            if layer.brightness != 1.0 or layer.contrast != 0.0:
                layer_img = self._adjust_brightness_contrast(
                    layer_img, layer.brightness, layer.contrast
                )

            # Apply transformations
            if layer.rotate:
                layer_img = layer_img.rotate(-layer.rotate, expand=True)
            if layer.flip_h:
                layer_img = layer_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if layer.flip_v:
                layer_img = layer_img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

            # Resize if needed
            target_width = layer.width or (img.width - layer.x)
            target_height = layer.height or (img.height - layer.y)

            if layer.resize_mode == "stretch":
                layer_img = layer_img.resize((target_width, target_height))
            elif layer.resize_mode == "fit":
                layer_img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            elif layer.resize_mode == "crop":
                # Center crop
                layer_img = self._center_crop(layer_img, target_width, target_height)

            # Apply dithering
            if layer.dither_mode == "floyd-steinberg":
                layer_img = layer_img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
                layer_img = layer_img.convert("L")
            elif layer.dither_mode == "threshold":
                layer_img = layer_img.point(lambda x: 255 if x > 128 else 0)

            # Paste onto main image
            img.paste(layer_img, (layer.x, layer.y))

        except Exception as e:
            error(f"Error rendering image layer: {e}")
            debug_manager.log_error(
                "render_image_layer",
                e,
                {
                    "layer_id": layer.id if hasattr(layer, "id") else "unknown",
                    "image_path": layer.image_path,
                },
            )

    def _adjust_brightness_contrast(
        self, img: Image.Image, brightness: float, contrast: float
    ) -> Image.Image:
        """Adjust image brightness and contrast."""
        # Convert to numpy array
        arr = np.array(img, dtype=np.float32)

        # Apply brightness
        arr = arr * brightness

        # Apply contrast
        if contrast != 0:
            arr = (arr - 128) * (1 + contrast) + 128

        # Clip values
        arr = np.clip(arr, 0, 255)

        return Image.fromarray(arr.astype(np.uint8))

    def _center_crop(self, img: Image.Image, width: int, height: int) -> Image.Image:
        """Center crop an image to target dimensions."""
        left = (img.width - width) // 2
        top = (img.height - height) // 2
        right = left + width
        bottom = top + height

        return img.crop((left, top, right, bottom))

    @timed_operation("render_to_base64")
    def render_to_base64(
        self,
        layers: list[Layer],
        width: int = 250,
        height: int = 128,
        background_color: int = 255,
        format: str = "PNG",
    ) -> str:
        """Render layers and return as base64 string."""
        img = self.render_layers(layers, width, height, background_color)
        debug(f"Converting rendered image to base64 ({format})")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        buffer.seek(0)

        base64_str = base64.b64encode(buffer.read()).decode("utf-8")
        debug(f"Base64 image size: {len(base64_str)} characters")
        return base64_str

    def render_to_binary(
        self,
        layers: list[Layer],
        width: int = 250,
        height: int = 128,
        background_color: int = 255,
    ) -> bytes:
        """Render layers and return as binary data for e-ink display."""
        img = self.render_layers(layers, width, height, background_color)

        # Convert to 1-bit
        img = img.convert("1", dither=Image.Dither.NONE)

        # Convert to binary array
        pixels = list(img.getdata())
        binary_data = bytearray()

        for i in range(0, len(pixels), 8):
            byte = 0
            for j in range(8):
                if i + j < len(pixels):
                    if pixels[i + j] > 0:
                        byte |= 1 << (7 - j)
            binary_data.append(byte)

        return bytes(binary_data)
