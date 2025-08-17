"""E-ink composer layers."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Union

import numpy as np


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


@dataclass
class RectangleLayer(Layer):
    type: str = field(default="rectangle", init=False)
    width: int = 10
    height: int = 10
    filled: bool = True
    color: int = 0  # 0=black, 255=white
    border_width: int = 1  # Border width for unfilled rectangles
