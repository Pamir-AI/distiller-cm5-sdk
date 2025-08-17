"""E-ink composer API models."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class TextLayerRequest(BaseModel):
    text: str = Field(..., description="Text to display")
    x: int = Field(0, description="X position")
    y: int = Field(0, description="Y position")
    color: int = Field(0, ge=0, le=255, description="Text color (0=black, 255=white)")
    font_size: int = Field(1, ge=1, le=5, description="Font scale factor")
    background: bool = Field(False, description="Add white background behind text")
    padding: int = Field(2, ge=0, description="Background padding in pixels")
    rotate: int = Field(0, description="Rotation in degrees")
    flip_h: bool = Field(False, description="Flip horizontally")
    flip_v: bool = Field(False, description="Flip vertically")


class RectangleLayerRequest(BaseModel):
    x: int = Field(0, description="X position")
    y: int = Field(0, description="Y position")
    width: int = Field(50, ge=1, description="Rectangle width")
    height: int = Field(30, ge=1, description="Rectangle height")
    filled: bool = Field(False, description="Fill rectangle")
    color: int = Field(0, ge=0, le=255, description="Rectangle color (0=black, 255=white)")
    border_width: int = Field(1, ge=1, description="Border width for unfilled rectangles")


class ImageLayerRequest(BaseModel):
    x: int = Field(0, description="X position")
    y: int = Field(0, description="Y position")
    resize_mode: Literal["stretch", "fit", "crop"] = Field("fit", description="Resize mode")
    dither_mode: Literal["floyd-steinberg", "threshold", "none"] = Field(
        "floyd-steinberg", description="Dithering mode"
    )
    brightness: float = Field(1.0, ge=0.1, le=2.0, description="Brightness adjustment")
    contrast: float = Field(0.0, ge=-1.0, le=1.0, description="Contrast adjustment")
    rotate: int = Field(0, description="Rotation in degrees")
    flip_h: bool = Field(False, description="Flip horizontally")
    flip_v: bool = Field(False, description="Flip vertically")
    width: int | None = Field(None, description="Custom width")
    height: int | None = Field(None, description="Custom height")


class PlaceholderRequest(BaseModel):
    x: int = Field(0, description="X position")
    y: int = Field(0, description="Y position")
    placeholder_type: Literal["ip", "qr"] = Field(..., description="Type of placeholder")
    width: int | None = Field(70, description="Width (for QR codes)")
    height: int | None = Field(70, description="Height (for QR codes)")
    color: int = Field(0, ge=0, le=255, description="Color (for IP text)")
    font_size: int = Field(1, ge=1, le=5, description="Font size (for IP text)")
    background: bool = Field(False, description="Background (for IP text)")


class UpdateLayerRequest(BaseModel):
    x: int | None = None
    y: int | None = None
    visible: bool | None = None
    text: str | None = None
    color: int | None = Field(None, ge=0, le=255)
    font_size: int | None = Field(None, ge=1, le=5)
    width: int | None = Field(None, ge=1)
    height: int | None = Field(None, ge=1)
    filled: bool | None = None


class DisplayRequest(BaseModel):
    partial: bool = Field(False, description="Use partial refresh")
    rotate: bool = Field(False, description="Rotate display")
    flip_h: bool = Field(False, description="Flip horizontally")
    flip_v: bool = Field(False, description="Flip vertically")


class RenderRequest(BaseModel):
    format: Literal["png", "bmp", "binary"] = Field("png", description="Output format")
    background_color: int = Field(255, ge=0, le=255, description="Background color")
    transformations: list[Literal["flip-h", "flip-v", "rotate-90", "invert"]] | None = None


class TemplateExportRequest(BaseModel):
    name: str = Field(..., description="Template name")
    description: str | None = Field(None, description="Template description")


class LayerResponse(BaseModel):
    id: str
    type: Literal["text", "image", "rectangle"]
    visible: bool
    x: int
    y: int
    text: str | None = None
    image_path: str | None = None
    width: int | None = None
    height: int | None = None
    color: int | None = None
    filled: bool | None = None


class CompositionResponse(BaseModel):
    width: int
    height: int
    layers: list[LayerResponse]
    layer_count: int


class PreviewResponse(BaseModel):
    image: str = Field(..., description="Base64 encoded PNG image")
    width: int
    height: int


class OperationResponse(BaseModel):
    success: bool
    message: str | None = None
    layer_id: str | None = None
    error: str | None = None


class HardwareInfoResponse(BaseModel):
    available: bool
    sdk_imported: bool
    hardware_init: bool | None = None
    hardware_status: str
    display_size: str | None = None
    width: int | None = None
    height: int | None = None
    firmware: str | None = None


class SystemInfoResponse(BaseModel):
    ip_address: str
    hardware_available: bool
    sdk_version: str | None = None


class TemplateInfo(BaseModel):
    name: str
    display_name: str
    created: str
    path: str
    layers_count: int


class TemplateListResponse(BaseModel):
    templates: list[TemplateInfo]


class TemplateData(BaseModel):
    template_version: str
    name: str
    created: str | None = None
    width: int
    height: int
    layers: list[dict[str, Any]]
