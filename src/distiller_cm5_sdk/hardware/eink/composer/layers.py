"""E-ink composer layers."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Union

import numpy as np


def validate_rotation(value: int) -> int:
    """Validate rotation value is 0, 90, 180, or 270."""
    if value not in (0, 90, 180, 270):
        raise ValueError(f"Invalid rotation {value}. Must be 0, 90, 180, or 270")
    return value


def validate_color(value: int) -> int:
    """Validate color value is between 0 and 255."""
    if not 0 <= value <= 255:
        raise ValueError(f"Invalid color {value}. Must be between 0 and 255")
    return value


@dataclass
class Layer:
    id: str
    type: str
    visible: bool = True
    x: int = 0
    y: int = 0


@dataclass
class ImageLayer(Layer):
    type: str = field(default="image", init=False)
    image_path: str | None = None
    image_data: np.ndarray | None = None
    resize_mode: Literal["stretch", "fit", "crop"] = "fit"
    dither_mode: Literal["floyd-steinberg", "threshold", "none"] = "floyd-steinberg"
    brightness: float = 1.0
    contrast: float = 0.0
    rotate: int = 0  # Rotation in degrees (0, 90, 180, 270)
    flip_h: bool = False  # Horizontal flip
    flip_v: bool = False  # Vertical flip
    crop_x: int | None = None  # X position for crop (None = center)
    crop_y: int | None = None  # Y position for crop (None = center)
    width: int | None = None  # Custom width (None = auto-calculate from canvas)
    height: int | None = None  # Custom height (None = auto-calculate from canvas)

    def __post_init__(self):
        self.rotate = validate_rotation(self.rotate)


@dataclass
class TextLayer(Layer):
    type: str = field(default="text", init=False)
    text: str = ""
    color: int = 0  # 0=black, 255=white
    rotate: int = 0  # Rotation in degrees (0, 90, 180, 270)
    flip_h: bool = False  # Horizontal flip
    flip_v: bool = False  # Vertical flip
    font_size: int = 1  # Font scale factor (1=normal, 2=double, etc.)
    background: bool = False  # Whether to draw white background
    padding: int = 2  # Padding around text background

    def __post_init__(self):
        self.rotate = validate_rotation(self.rotate)
        self.color = validate_color(self.color)


@dataclass
class RectangleLayer(Layer):
    type: str = field(default="rectangle", init=False)
    width: int = 10
    height: int = 10
    filled: bool = True
    color: int = 0  # 0=black, 255=white
    border_width: int = 1  # Border width for unfilled rectangles

    def __post_init__(self):
        self.color = validate_color(self.color)
