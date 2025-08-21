"""
E-ink Composer Module for Distiller CM5 SDK
Provides layer-based composition system for e-ink displays with text rendering,
templates, and image processing capabilities.
"""

from .layers import ImageLayer, Layer, RectangleLayer, TextLayer
from .services import ComposerService, HardwareService, RenderService, TemplateService

__version__ = "2.0.0"
__all__ = [
    "ComposerService",
    "RenderService",
    "HardwareService",
    "TemplateService",
    "Layer",
    "ImageLayer",
    "TextLayer",
    "RectangleLayer",
]
