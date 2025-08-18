#!/usr/bin/env python3
"""E-ink composer web UI."""

import base64
import json
import os
import socket
import sys
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

from .. import Display, DisplayMode
from .core import EinkComposer
from .layers import ImageLayer, RectangleLayer, TextLayer
from .models import (
    CompositionResponse,
    DisplayRequest,
    HardwareInfoResponse,
    ImageLayerRequest,
    LayerResponse,
    OperationResponse,
    PlaceholderRequest,
    PreviewResponse,
    RectangleLayerRequest,
    RenderRequest,
    SystemInfoResponse,
    TemplateData,
    TemplateExportRequest,
    TemplateInfo,
    TemplateListResponse,
    TextLayerRequest,
    UpdateLayerRequest,
)
from .templates import TemplateRenderer

compositions: dict[str, EinkComposer] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting E-ink Composer FastAPI server...")

    try:
        # Test hardware access with acquire/release pattern
        with Display(auto_init=False):
            print("Hardware initialized successfully")
    except Exception as e:
        print(f"FATAL: E-ink hardware not available: {e}")
        print("This application requires Distiller CM5 e-ink hardware to run.")
        sys.exit(1)

    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)

    yield

    print("Shutting down E-ink Composer server...")
    compositions.clear()


app = FastAPI(
    title="E-ink Composer API",
    description="Web UI for composing e-ink display layouts",
    version="1.0.0",
    lifespan=lifespan,
)

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def get_session_id(request: Request, response: Response) -> str:
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie(key="session_id", value=session_id, httponly=True)
    return session_id


def get_composition(session_id: str = Depends(get_session_id)) -> EinkComposer:
    if session_id not in compositions:
        compositions[session_id] = EinkComposer(250, 128)
    return compositions[session_id]


def array_to_base64(img_array: np.ndarray) -> str:
    pil_img = Image.fromarray(img_array, mode="L")
    buffer = BytesIO()
    pil_img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/preview", response_model=PreviewResponse)
async def preview(composer: EinkComposer = Depends(get_composition)):
    img_array = composer.render()
    return PreviewResponse(
        image=array_to_base64(img_array), width=composer.width, height=composer.height
    )


@app.get("/api/layers", response_model=list[LayerResponse])
async def get_layers(composer: EinkComposer = Depends(get_composition)):
    return composer.get_layer_info()


@app.post("/api/add-text", response_model=OperationResponse)
async def add_text(request: TextLayerRequest, composer: EinkComposer = Depends(get_composition)):
    try:
        text = request.text.upper()
        layer_id = f"text_{len(composer.layers)}"

        composer.add_text_layer(
            layer_id=layer_id,
            text=text,
            x=request.x,
            y=request.y,
            color=request.color,
            font_size=request.font_size,
            background=request.background,
            padding=request.padding,
            rotate=request.rotate,
            flip_h=request.flip_h,
            flip_v=request.flip_v,
        )

        return OperationResponse(success=True, layer_id=layer_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/add-rect", response_model=OperationResponse)
async def add_rect(
    request: RectangleLayerRequest, composer: EinkComposer = Depends(get_composition)
):
    try:
        layer_id = f"rect_{len(composer.layers)}"

        composer.add_rectangle_layer(
            layer_id=layer_id,
            x=request.x,
            y=request.y,
            width=request.width,
            height=request.height,
            filled=request.filled,
            color=request.color,
            border_width=request.border_width,
        )

        return OperationResponse(success=True, layer_id=layer_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/add-image", response_model=OperationResponse)
async def add_image(
    file: UploadFile = File(...),
    x: int = 0,
    y: int = 0,
    resize_mode: str = "fit",
    dither_mode: str = "floyd-steinberg",
    composer: EinkComposer = Depends(get_composition),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No image selected")

    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        layer_id = f"image_{len(composer.layers)}"

        composer.add_image_layer(
            layer_id=layer_id,
            image_path=tmp_path,
            x=x,
            y=y,
            resize_mode=resize_mode,
            dither_mode=dither_mode,
        )

        return OperationResponse(success=True, layer_id=layer_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


@app.delete("/api/layer/{layer_id}", response_model=OperationResponse)
async def remove_layer(layer_id: str, composer: EinkComposer = Depends(get_composition)):
    success = composer.remove_layer(layer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Layer not found")
    return OperationResponse(success=True)


@app.post("/api/layer/{layer_id}/toggle", response_model=OperationResponse)
async def toggle_layer(layer_id: str, composer: EinkComposer = Depends(get_composition)):
    success = composer.toggle_layer(layer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Layer not found")
    return OperationResponse(success=True)


@app.patch("/api/layer/{layer_id}", response_model=OperationResponse)
async def update_layer(
    layer_id: str, request: UpdateLayerRequest, composer: EinkComposer = Depends(get_composition)
):
    update_dict = request.dict(exclude_unset=True)
    success = composer.update_layer(layer_id, **update_dict)
    if not success:
        raise HTTPException(status_code=404, detail="Layer not found")
    return OperationResponse(success=True)


@app.post("/api/add-placeholder", response_model=OperationResponse)
async def add_placeholder(
    request: PlaceholderRequest, composer: EinkComposer = Depends(get_composition)
):
    try:
        if request.placeholder_type == "ip":
            layer_id = f"ip_placeholder_{len(composer.layers)}"

            composer.add_text_layer(
                layer_id=layer_id,
                text="$IP_ADDRESS",
                x=request.x,
                y=request.y,
                color=request.color,
                font_size=request.font_size,
                background=request.background,
            )

            composer.layers[-1].placeholder_type = "ip"

        elif request.placeholder_type == "qr":
            layer_id = f"qr_placeholder_{len(composer.layers)}"

            width = request.width or 70
            height = request.height or 70

            placeholder_img = np.full((height, width), 255, dtype=np.uint8)
            placeholder_img[0:2, :] = 0
            placeholder_img[-2:, :] = 0
            placeholder_img[:, 0:2] = 0
            placeholder_img[:, -2:] = 0

            center_y, center_x = height // 2, width // 2
            if height > 10 and width > 20:
                placeholder_img[
                    max(0, center_y - 5) : min(height, center_y + 5),
                    max(0, center_x - 10) : min(width, center_x + 10),
                ] = 0

            layer = ImageLayer(
                id=layer_id,
                x=request.x,
                y=request.y,
                image_data=placeholder_img,
                width=width,
                height=height,
                image_path=None,
            )

            layer.placeholder_type = "qr"
            composer.layers.append(layer)

        else:
            raise ValueError(f"Unknown placeholder type: {request.placeholder_type}")

        return OperationResponse(success=True, layer_id=layer_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/clear", response_model=OperationResponse)
async def clear_all(composer: EinkComposer = Depends(get_composition)):
    composer.layers.clear()
    return OperationResponse(success=True)


@app.post("/api/display", response_model=OperationResponse)
async def display_hardware(
    request: DisplayRequest, composer: EinkComposer = Depends(get_composition)
):
    try:
        mode = DisplayMode.PARTIAL if request.partial else DisplayMode.FULL

        # Convert boolean rotate to RotationMode
        from .. import RotationMode

        rotation = RotationMode.ROTATE_90 if request.rotate else RotationMode.NONE

        success = composer.display(
            mode=mode, rotation=rotation, flip_h=request.flip_h, flip_v=request.flip_v
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to display on hardware")

        return OperationResponse(success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Display error: {str(e)}")


@app.post("/api/hardware/clear", response_model=OperationResponse)
async def clear_hardware(composer: EinkComposer = Depends(get_composition)):
    try:
        success = composer.clear_display()

        if not success:
            raise HTTPException(status_code=500, detail="Failed to clear display")

        return OperationResponse(success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clear error: {str(e)}")


@app.get("/api/hardware/info", response_model=HardwareInfoResponse)
async def hardware_info():
    info = HardwareInfoResponse(available=True, sdk_imported=True, hardware_status="SDK available")

    try:
        display = Display(auto_init=False)

        try:
            # Use context manager to acquire/release hardware
            with display:
                width, height = display.get_dimensions()
                info.display_size = f"{width}x{height}"
                info.width = width
                info.height = height
                info.hardware_init = True
                info.hardware_status = "Available and working"
        except Exception as e:
            info.display_size = "128x250 (default)"
            info.hardware_init = False
            info.hardware_status = f"SDK available but hardware init failed: {e}"

    except Exception as e:
        info.hardware_status = f"SDK available but Display creation failed: {e}"

    return info


@app.post("/api/save-template", response_model=OperationResponse)
async def save_template(composer: EinkComposer = Depends(get_composition)):
    template_data = composer.to_dict()
    template_data["template_version"] = "1.0"
    template_data["created_for"] = "tunnel_service"

    for i, layer in enumerate(composer.layers):
        if hasattr(layer, "placeholder_type"):
            template_data["layers"][i]["placeholder_type"] = layer.placeholder_type

    return OperationResponse(success=True, message=json.dumps(template_data))


@app.post("/api/load-template", response_model=OperationResponse)
async def load_template(template: TemplateData, session_id: str = Depends(get_session_id)):
    try:
        composer = EinkComposer(template.width, template.height)
        composer.from_dict(template.dict())

        compositions[session_id] = composer

        return OperationResponse(success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download-png")
async def download_png(composer: EinkComposer = Depends(get_composition)):
    img_array = composer.render()
    pil_img = Image.fromarray(img_array, mode="L")

    buffer = BytesIO()
    pil_img.save(buffer, format="PNG")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={"Content-Disposition": "attachment; filename=eink_composition.png"},
    )


@app.post("/api/export-template", response_model=OperationResponse)
async def export_template(
    request: TemplateExportRequest, composer: EinkComposer = Depends(get_composition)
):
    try:
        template_name = request.name.replace("/", "_").replace("\\", "_")

        template_dir = f"templates/{template_name}"
        os.makedirs(template_dir, exist_ok=True)

        template_data = composer.to_dict()
        template_data["template_version"] = "1.0"
        template_data["name"] = template_name
        template_data["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if request.description:
            template_data["description"] = request.description

        template_json_path = os.path.join(template_dir, "template.json")
        with open(template_json_path, "w") as f:
            json.dump(template_data, f, indent=2)

        return OperationResponse(success=True, message=f"Template package saved to {template_dir}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/import-template", response_model=OperationResponse)
async def import_template(template_data: dict[str, Any], session_id: str = Depends(get_session_id)):
    try:
        composer = EinkComposer(template_data.get("width", 250), template_data.get("height", 128))
        composer.from_dict(template_data)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get IP address: {e}")

        for layer in composer.layers:
            if hasattr(layer, "placeholder_type") and layer.placeholder_type == "ip":
                if isinstance(layer, TextLayer):
                    layer.text = ip_address

        compositions[session_id] = composer

        return OperationResponse(success=True, message="Template imported successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/list-templates", response_model=TemplateListResponse)
async def list_templates():
    try:
        templates = []
        templates_dir = "templates"

        if os.path.exists(templates_dir):
            for item in os.listdir(templates_dir):
                item_path = os.path.join(templates_dir, item)
                template_json_path = os.path.join(item_path, "template.json")

                if os.path.isdir(item_path) and os.path.exists(template_json_path):
                    try:
                        with open(template_json_path) as f:
                            template_data = json.load(f)

                        templates.append(
                            TemplateInfo(
                                name=item,
                                display_name=template_data.get("name", item),
                                created=template_data.get("created", ""),
                                path=item_path,
                                layers_count=len(template_data.get("layers", [])),
                            )
                        )
                    except Exception as e:
                        print(f"Warning: Could not read template {item}: {e}")

        return TemplateListResponse(templates=templates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system-info", response_model=SystemInfoResponse)
async def get_system_info():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get IP address: {e}")

    return SystemInfoResponse(ip_address=ip_address, hardware_available=True)


@app.get("/templates/{path:path}")
async def serve_template_files(path: str):
    file_path = Path("templates") / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)
