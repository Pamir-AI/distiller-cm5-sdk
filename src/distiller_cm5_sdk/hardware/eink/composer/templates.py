"""E-ink composer templates."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

try:
    import qrcode
    from PIL import Image

    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    print("Warning: qrcode library not available. QR code placeholders will not work.")

from .. import Display, DisplayMode
from .core import EinkComposer


class TemplateRenderer:
    def __init__(self, template_path: str):
        self.template_path = Path(template_path)
        self.template_dir = self.template_path.parent
        self.template = self._load_template()

    def _load_template(self) -> dict:
        try:
            with open(self.template_path) as f:
                template = json.load(f)

            # Validate template structure
            if "layers" not in template:
                raise ValueError("Template must have 'layers' field")

            return template
        except Exception as e:
            raise Exception(f"Failed to load template {self.template_path}: {e}")

    def _resolve_image_path(self, image_path: str) -> str:
        path = Path(image_path)
        if path.is_absolute():
            return str(path)
        else:
            # Resolve relative to template directory
            resolved = self.template_dir / path
            return str(resolved.resolve())

    def _generate_qr_code_file(
        self, data: str, output_path: str, size: tuple, error_correction: str = "M"
    ) -> str:
        if not QRCODE_AVAILABLE:
            raise RuntimeError("qrcode library not available")

        # Map error correction levels
        correction_map = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }

        qr = qrcode.QRCode(
            version=1,
            error_correction=correction_map.get(error_correction, qrcode.constants.ERROR_CORRECT_M),
            box_size=max(1, min(size) // 25),  # Adjust box size based on target size
            border=1,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # Generate and save PIL image
        pil_img = qr.make_image(fill_color="black", back_color="white")
        pil_img = pil_img.resize(size, Image.NEAREST)
        pil_img.save(output_path)

        return output_path

    def render(
        self, ip_address: str | None = None, tunnel_url: str | None = None, **kwargs
    ) -> EinkComposer:
        # Get template dimensions
        width = self.template.get("width", 122)
        height = self.template.get("height", 250)

        # Create composer
        composer = EinkComposer(width, height)

        # Track temporary files for cleanup
        temp_files = []

        try:
            # Process each layer from the template
            for layer_data in self.template.get("layers", []):
                if not layer_data.get("visible", True):
                    continue

                layer_type = layer_data.get("type")
                placeholder_type = layer_data.get("placeholder_type")

                # Handle placeholder layers
                if placeholder_type == "ip" and ip_address:
                    # IP address text layer
                    composer.add_text_layer(
                        layer_id=layer_data.get("id", "ip_text"),
                        text=ip_address,
                        x=layer_data.get("x", 0),
                        y=layer_data.get("y", 0),
                        color=layer_data.get("color", 0),
                        font_size=layer_data.get("font_size", 1),
                        rotate=layer_data.get("rotate", 0),
                        flip_h=layer_data.get("flip_h", False),
                        flip_v=layer_data.get("flip_v", False),
                        background=layer_data.get("background", False),
                        padding=layer_data.get("padding", 2),
                    )

                elif placeholder_type == "qr" and tunnel_url:
                    # QR code image layer
                    if QRCODE_AVAILABLE:
                        # Generate QR code to temp file
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                            qr_width = layer_data.get("width", 70)
                            qr_height = layer_data.get("height", 70)
                            error_correction = layer_data.get("error_correction", "M")

                            qr_path = self._generate_qr_code_file(
                                tunnel_url, tmp.name, (qr_width, qr_height), error_correction
                            )
                            temp_files.append(qr_path)

                        composer.add_image_layer(
                            layer_id=layer_data.get("id", "qr_code"),
                            image_path=qr_path,
                            x=layer_data.get("x", 0),
                            y=layer_data.get("y", 0),
                            width=qr_width,
                            height=qr_height,
                            resize_mode="stretch",
                        )

                elif placeholder_type == "text":
                    # Generic text placeholder
                    placeholder_key = layer_data.get("placeholder_key", "text")
                    text_value = kwargs.get(placeholder_key, "")
                    if text_value:
                        composer.add_text_layer(
                            layer_id=layer_data.get("id", f"text_{placeholder_key}"),
                            text=str(text_value),
                            x=layer_data.get("x", 0),
                            y=layer_data.get("y", 0),
                            color=layer_data.get("color", 0),
                            font_size=layer_data.get("font_size", 1),
                            rotate=layer_data.get("rotate", 0),
                            flip_h=layer_data.get("flip_h", False),
                            flip_v=layer_data.get("flip_v", False),
                            background=layer_data.get("background", False),
                            padding=layer_data.get("padding", 2),
                        )

                # Handle regular layers
                elif layer_type == "text":
                    composer.add_text_layer(
                        layer_id=layer_data.get("id", f"text_{len(composer.layers)}"),
                        text=layer_data.get("text", ""),
                        x=layer_data.get("x", 0),
                        y=layer_data.get("y", 0),
                        color=layer_data.get("color", 0),
                        font_size=layer_data.get("font_size", 1),
                        rotate=layer_data.get("rotate", 0),
                        flip_h=layer_data.get("flip_h", False),
                        flip_v=layer_data.get("flip_v", False),
                        background=layer_data.get("background", False),
                        padding=layer_data.get("padding", 2),
                    )

                elif layer_type == "image":
                    image_path = layer_data.get("image_path")
                    if image_path:
                        # Resolve image path relative to template
                        resolved_path = self._resolve_image_path(image_path)

                        composer.add_image_layer(
                            layer_id=layer_data.get("id", f"image_{len(composer.layers)}"),
                            image_path=resolved_path,
                            x=layer_data.get("x", 0),
                            y=layer_data.get("y", 0),
                            resize_mode=layer_data.get("resize_mode", "fit"),
                            dither_mode=layer_data.get("dither_mode", "floyd-steinberg"),
                            brightness=layer_data.get("brightness", 1.0),
                            contrast=layer_data.get("contrast", 0.0),
                            rotate=layer_data.get("rotate", 0),
                            flip_h=layer_data.get("flip_h", False),
                            flip_v=layer_data.get("flip_v", False),
                            crop_x=layer_data.get("crop_x"),
                            crop_y=layer_data.get("crop_y"),
                            width=layer_data.get("width"),
                            height=layer_data.get("height"),
                        )

                elif layer_type == "rectangle":
                    composer.add_rectangle_layer(
                        layer_id=layer_data.get("id", f"rect_{len(composer.layers)}"),
                        x=layer_data.get("x", 0),
                        y=layer_data.get("y", 0),
                        width=layer_data.get("width", 10),
                        height=layer_data.get("height", 10),
                        filled=layer_data.get("filled", True),
                        color=layer_data.get("color", 0),
                        border_width=layer_data.get("border_width", 1),
                    )

            return composer

        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    Path(temp_file).unlink(missing_ok=True)
                except:
                    pass

    def render_and_display(
        self,
        ip_address: str | None = None,
        tunnel_url: str | None = None,
        mode: DisplayMode = DisplayMode.FULL,
        **kwargs,
    ) -> bool:
        try:
            # Render template to composer
            composer = self.render(ip_address, tunnel_url, **kwargs)

            # Display on hardware
            return composer.display(mode)

        except Exception as e:
            print(f"Failed to render and display template: {e}")
            return False

    def render_and_save(
        self,
        output_path: str,
        ip_address: str | None = None,
        tunnel_url: str | None = None,
        format: str = "png",
        **kwargs,
    ) -> bool:
        try:
            # Render template to composer
            composer = self.render(ip_address, tunnel_url, **kwargs)

            # Save to file
            composer.save(output_path, format)
            return True

        except Exception as e:
            print(f"Failed to render and save template: {e}")
            return False


def create_template_from_dict(template_dict: dict, save_path: str | None = None) -> dict[str, Any]:
    # Validate required fields
    if "layers" not in template_dict:
        template_dict["layers"] = []

    # Set defaults
    template_dict.setdefault("template_version", "1.0")
    template_dict.setdefault("width", 122)
    template_dict.setdefault("height", 250)

    # Save if path provided
    if save_path:
        with open(save_path, "w") as f:
            json.dump(template_dict, f, indent=2)

    return template_dict


def create_template_from_composer(
    composer: EinkComposer, template_path: str, copy_images: bool = False
) -> None:
    template_dir = Path(template_path).parent
    template_dir.mkdir(parents=True, exist_ok=True)

    # Convert composer to template format
    template = {
        "template_version": "1.0",
        "width": composer.width,
        "height": composer.height,
        "layers": [],
    }

    for layer in composer.layers:
        layer_dict = {
            "id": layer.id,
            "type": layer.type,
            "visible": layer.visible,
            "x": layer.x,
            "y": layer.y,
        }

        # Add type-specific properties
        if layer.type == "text":
            layer_dict.update(
                {
                    "text": layer.text,
                    "color": layer.color,
                    "font_size": layer.font_size,
                    "rotate": layer.rotate,
                    "flip_h": layer.flip_h,
                    "flip_v": layer.flip_v,
                    "background": layer.background,
                    "padding": layer.padding,
                }
            )
        elif layer.type == "image":
            if copy_images and layer.image_path:
                # Copy image to template directory
                src_path = Path(layer.image_path)
                if src_path.exists():
                    dst_path = template_dir / src_path.name
                    if src_path != dst_path:
                        import shutil

                        shutil.copy2(src_path, dst_path)
                    layer_dict["image_path"] = src_path.name
                else:
                    layer_dict["image_path"] = layer.image_path
            else:
                layer_dict["image_path"] = layer.image_path

            layer_dict.update(
                {
                    "resize_mode": layer.resize_mode,
                    "dither_mode": layer.dither_mode,
                    "brightness": layer.brightness,
                    "contrast": layer.contrast,
                    "rotate": layer.rotate,
                    "flip_h": layer.flip_h,
                    "flip_v": layer.flip_v,
                    "crop_x": layer.crop_x,
                    "crop_y": layer.crop_y,
                    "width": layer.width,
                    "height": layer.height,
                }
            )
        elif layer.type == "rectangle":
            layer_dict.update(
                {
                    "width": layer.width,
                    "height": layer.height,
                    "filled": layer.filled,
                    "color": layer.color,
                    "border_width": layer.border_width,
                }
            )

        template["layers"].append(layer_dict)

    # Save template
    with open(template_path, "w") as f:
        json.dump(template, f, indent=2)
