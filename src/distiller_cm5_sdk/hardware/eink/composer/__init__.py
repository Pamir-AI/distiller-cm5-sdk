"""
E-ink Composer Module for Distiller CM5 SDK
Provides layer-based composition system for e-ink displays with text rendering,
templates, and image processing capabilities.
"""

from .core import EinkComposer
from .layers import ImageLayer, Layer, RectangleLayer, TextLayer
from .templates import TemplateRenderer, create_template_from_dict
from .text import FONT_HEIGHT, FONT_WIDTH, measure_text, render_text

__version__ = "1.0.0"
__all__ = [
    "EinkComposer",
    "Layer",
    "ImageLayer",
    "TextLayer",
    "RectangleLayer",
    "TemplateRenderer",
    "create_template_from_dict",
    "render_text",
    "measure_text",
    "FONT_WIDTH",
    "FONT_HEIGHT",
]
