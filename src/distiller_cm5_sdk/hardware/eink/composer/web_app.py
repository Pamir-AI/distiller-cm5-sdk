"""E-ink Composer Web Application - Clean FastAPI backend."""

import os
import tempfile
from pathlib import Path
from typing import Optional

try:
    import qrcode

    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
    print("Warning: qrcode library not available. QR code placeholders will not work.")

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .models import (
    DisplayRequest,
    ImageLayerRequest,
    LayerResponse,
    OperationResponse,
    PlaceholderRequest,
    PreviewResponse,
    RectangleLayerRequest,
    RenderRequest,
    TemplateExportRequest,
    TextLayerRequest,
    UpdateLayerRequest,
)
from .services import ComposerService, HardwareService, RenderService, TemplateService
from .services.debug import debug, debug_manager, error, info, warning

# Initialize FastAPI app
app = FastAPI(
    title="E-ink Composer API",
    description="Web-based e-ink display composer",
    version="1.0.0",
)


# Add debug middleware
@app.middleware("http")
async def debug_middleware(request, call_next):
    """Log all requests and responses when debug mode is enabled."""
    if debug_manager.is_enabled():
        import time

        start_time = time.time()

        # Log request
        debug(f"Request: {request.method} {request.url.path}")
        if request.url.query:
            debug(f"  Query: {request.url.query}")

        # Process request
        response = await call_next(request)

        # Log response
        duration = time.time() - start_time
        debug(f"Response: {response.status_code} in {duration:.3f}s")
        debug_manager.log_performance(f"{request.method} {request.url.path}", duration)

        return response
    else:
        return await call_next(request)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
composer = ComposerService()
renderer = RenderService()
hardware = HardwareService()
templates = TemplateService()

# Update composer dimensions based on hardware
if hardware.is_available():
    width, height = hardware.get_dimensions()
    composer.width = width
    composer.height = height
    info(f"Composer dimensions set to hardware: {width}x{height}")
else:
    warning("Hardware not available, using default dimensions")


# --- Layer Management Endpoints ---


@app.get("/api/layers", response_model=list[LayerResponse])
async def get_layers():
    """Get all layers in composition."""
    layers = composer.get_layers()
    debug(f"Returning {len(layers)} layers")
    return [
        LayerResponse(
            id=layer.id,
            type=layer.type,
            visible=layer.visible,
            x=layer.x,
            y=layer.y,
            text=getattr(layer, "text", None),
            width=getattr(layer, "width", None),
            height=getattr(layer, "height", None),
            color=getattr(layer, "color", None),
            filled=getattr(layer, "filled", None),
        )
        for layer in layers
    ]


@app.post("/api/layers/text", response_model=OperationResponse)
async def add_text_layer(request: TextLayerRequest):
    """Add a text layer."""
    try:
        # Validate position is within canvas bounds
        if request.x < 0 or request.x > composer.width:
            raise HTTPException(400, f"X position {request.x} out of bounds (0-{composer.width})")
        if request.y < 0 or request.y > composer.height:
            raise HTTPException(400, f"Y position {request.y} out of bounds (0-{composer.height})")

        layer_id = composer.add_text_layer(
            text=request.text,
            x=request.x,
            y=request.y,
            color=request.color,
            font_size=request.font_size,
            background=request.background,
            padding=request.padding,
        )
        info(f"Text layer added: {layer_id} at ({request.x}, {request.y})")
        return OperationResponse(success=True, layer_id=layer_id, message="Text layer added")
    except HTTPException:
        raise
    except Exception as e:
        error(f"Failed to add text layer: {e}")
        debug_manager.log_error("add_text_layer", e, {"request": request.dict()})
        raise HTTPException(500, f"Failed to add text layer: {str(e)}")


@app.post("/api/layers/rectangle", response_model=OperationResponse)
async def add_rectangle_layer(request: RectangleLayerRequest):
    """Add a rectangle layer."""
    try:
        # Validate bounds
        if request.x < 0 or request.x + request.width > composer.width:
            raise HTTPException(400, f"Rectangle exceeds horizontal bounds (0-{composer.width})")
        if request.y < 0 or request.y + request.height > composer.height:
            raise HTTPException(400, f"Rectangle exceeds vertical bounds (0-{composer.height})")

        layer_id = composer.add_rectangle_layer(
            x=request.x,
            y=request.y,
            width=request.width,
            height=request.height,
            filled=request.filled,
            color=request.color,
            border_width=request.border_width,
        )
        info(f"Rectangle layer added: {layer_id} at ({request.x}, {request.y})")
        return OperationResponse(success=True, layer_id=layer_id, message="Rectangle layer added")
    except HTTPException:
        raise
    except Exception as e:
        error(f"Failed to add rectangle layer: {e}")
        debug_manager.log_error("add_rectangle_layer", e, {"request": request.dict()})
        raise HTTPException(500, f"Failed to add rectangle layer: {str(e)}")


@app.post("/api/layers/image", response_model=OperationResponse)
async def add_image_layer(
    file: UploadFile = File(...),
    x: int = 0,
    y: int = 0,
    width: int | None = None,
    height: int | None = None,
    resize_mode: str = "fit",
    dither_mode: str = "floyd-steinberg",
):
    """Add an image layer."""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                400, f"Invalid file type: {file.content_type}. Please upload an image file."
            )

        # Validate file size (max 10MB)
        if file.size and file.size > 10 * 1024 * 1024:
            raise HTTPException(400, "File too large. Maximum size is 10MB.")

        # Validate position
        if x < 0 or x > composer.width:
            raise HTTPException(400, f"X position {x} out of bounds (0-{composer.width})")
        if y < 0 or y > composer.height:
            raise HTTPException(400, f"Y position {y} out of bounds (0-{composer.height})")

        # Save uploaded file with proper permissions
        import os

        temp_dir = Path("/tmp/eink_composer")
        temp_dir.mkdir(mode=0o777, exist_ok=True)

        file_path = temp_dir / f"upload_{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Ensure file is readable by the distiller user/group
        os.chmod(file_path, 0o666)

        layer_id = composer.add_image_layer(
            image_path=str(file_path),
            x=x,
            y=y,
            width=width,
            height=height,
            resize_mode=resize_mode,
            dither_mode=dither_mode,
        )

        info(f"Image layer added: {layer_id} from {file.filename} at ({x}, {y})")
        return OperationResponse(success=True, layer_id=layer_id, message="Image layer added")
    except HTTPException:
        raise
    except Exception as e:
        error(f"Failed to add image layer: {e}")
        debug_manager.log_error("add_image_layer", e, {"filename": file.filename, "x": x, "y": y})
        raise HTTPException(500, f"Failed to add image layer: {str(e)}")


@app.post("/api/layers/placeholder", response_model=OperationResponse)
async def add_placeholder(request: PlaceholderRequest):
    """Add a placeholder (IP or QR code)."""
    try:
        # Validate position
        if request.x < 0 or request.x > composer.width:
            raise HTTPException(400, f"X position {request.x} out of bounds (0-{composer.width})")
        if request.y < 0 or request.y > composer.height:
            raise HTTPException(400, f"Y position {request.y} out of bounds (0-{composer.height})")

        if request.placeholder_type == "ip":
            # Add IP address text
            ip = hardware.get_ip_address()
            layer_id = composer.add_text_layer(
                text=ip,
                x=request.x,
                y=request.y,
                color=request.color or 0,
                font_size=request.font_size or 1,
                background=request.background or False,
            )
        elif request.placeholder_type == "qr":
            if not HAS_QRCODE:
                # Fallback: create a placeholder rectangle with text
                layer_id = composer.add_rectangle_layer(
                    x=request.x,
                    y=request.y,
                    width=request.width or 70,
                    height=request.height or 70,
                    filled=False,
                    color=0,
                    border_width=2,
                )
                # Add text in the middle
                ip = hardware.get_ip_address()
                composer.add_text_layer(
                    text="QR",
                    x=request.x + (request.width or 70) // 2 - 10,
                    y=request.y + (request.height or 70) // 2 - 6,
                    color=0,
                    font_size=1,
                )
            else:
                # Generate QR code
                ip = hardware.get_ip_address()
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=2,
                    border=1,
                )
                qr.add_data(f"http://{ip}:5000")
                qr.make(fit=True)

                qr_img = qr.make_image(fill_color="black", back_color="white")

                # Save QR code with proper permissions
                import os

                temp_path = Path("/tmp/eink_composer/qr_code.png")
                temp_path.parent.mkdir(mode=0o777, exist_ok=True)
                qr_img.save(temp_path)
                os.chmod(temp_path, 0o666)

                # Add as image layer
                layer_id = composer.add_image_layer(
                    image_path=str(temp_path),
                    x=request.x,
                    y=request.y,
                    width=request.width or 70,
                    height=request.height or 70,
                )
        else:
            raise HTTPException(
                status_code=400, detail=f"Invalid placeholder type: {request.placeholder_type}"
            )

        info(f"Placeholder added: {request.placeholder_type} at ({request.x}, {request.y})")
        return OperationResponse(
            success=True,
            layer_id=layer_id,
            message=f"{request.placeholder_type.upper()} placeholder added",
        )
    except HTTPException:
        raise
    except Exception as e:
        error(f"Failed to add placeholder: {e}")
        debug_manager.log_error("add_placeholder", e, {"request": request.dict()})
        raise HTTPException(500, f"Failed to add placeholder: {str(e)}")


@app.put("/api/layers/{layer_id}", response_model=OperationResponse)
async def update_layer(layer_id: str, request: UpdateLayerRequest):
    """Update layer properties."""
    try:
        updates = request.dict(exclude_unset=True)

        # Validate position updates if provided
        if "x" in updates and (updates["x"] < 0 or updates["x"] > composer.width):
            raise HTTPException(
                400, f"X position {updates['x']} out of bounds (0-{composer.width})"
            )
        if "y" in updates and (updates["y"] < 0 or updates["y"] > composer.height):
            raise HTTPException(
                400, f"Y position {updates['y']} out of bounds (0-{composer.height})"
            )

        success = composer.update_layer(layer_id, **updates)

        if not success:
            raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")

        info(f"Layer updated: {layer_id} with {list(updates.keys())}")
        return OperationResponse(success=True, message="Layer updated")
    except HTTPException:
        raise
    except Exception as e:
        error(f"Failed to update layer {layer_id}: {e}")
        debug_manager.log_error("update_layer", e, {"layer_id": layer_id, "updates": updates})
        raise HTTPException(500, f"Failed to update layer: {str(e)}")


@app.delete("/api/layers/{layer_id}", response_model=OperationResponse)
async def delete_layer(layer_id: str):
    """Delete a layer."""
    try:
        success = composer.remove_layer(layer_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")

        info(f"Layer deleted: {layer_id}")
        return OperationResponse(success=True, message="Layer deleted")
    except HTTPException:
        raise
    except Exception as e:
        error(f"Failed to delete layer {layer_id}: {e}")
        debug_manager.log_error("delete_layer", e, {"layer_id": layer_id})
        raise HTTPException(500, f"Failed to delete layer: {str(e)}")


@app.post("/api/layers/{layer_id}/toggle", response_model=OperationResponse)
async def toggle_layer_visibility(layer_id: str):
    """Toggle layer visibility."""
    try:
        success = composer.toggle_layer(layer_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")

        info(f"Layer visibility toggled: {layer_id}")
        return OperationResponse(success=True, message="Layer visibility toggled")
    except HTTPException:
        raise
    except Exception as e:
        error(f"Failed to toggle layer {layer_id}: {e}")
        debug_manager.log_error("toggle_layer", e, {"layer_id": layer_id})
        raise HTTPException(500, f"Failed to toggle layer: {str(e)}")


@app.post("/api/layers/{layer_id}/reorder", response_model=OperationResponse)
async def reorder_layer(layer_id: str, new_index: int):
    """Change layer order."""
    success = composer.reorder_layer(layer_id, new_index)

    if not success:
        raise HTTPException(status_code=400, detail="Invalid layer or index")

    return OperationResponse(success=True, message="Layer reordered")


@app.delete("/api/layers", response_model=OperationResponse)
async def clear_all_layers():
    """Clear all layers."""
    composer.clear()
    return OperationResponse(success=True, message="All layers cleared")


# --- Rendering Endpoints ---


@app.get("/api/preview", response_model=PreviewResponse)
async def get_preview():
    """Generate preview of current composition."""
    layers = composer.get_visible_layers()
    base64_image = renderer.render_to_base64(layers, composer.width, composer.height)

    return PreviewResponse(
        image=f"data:image/png;base64,{base64_image}",
        width=composer.width,
        height=composer.height,
    )


@app.post("/api/render", response_model=PreviewResponse)
async def render_composition(request: RenderRequest):
    """Render composition with specific settings."""
    layers = composer.get_visible_layers()

    if request.format == "png":
        base64_image = renderer.render_to_base64(
            layers,
            composer.width,
            composer.height,
            request.background_color,
            format="PNG",
        )
        return PreviewResponse(
            image=f"data:image/png;base64,{base64_image}",
            width=composer.width,
            height=composer.height,
        )
    elif request.format == "bmp":
        base64_image = renderer.render_to_base64(
            layers,
            composer.width,
            composer.height,
            request.background_color,
            format="BMP",
        )
        return PreviewResponse(
            image=f"data:image/bmp;base64,{base64_image}",
            width=composer.width,
            height=composer.height,
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")


# --- Hardware Endpoints ---


@app.post("/api/display", response_model=OperationResponse)
async def display_on_hardware(request: DisplayRequest):
    """Display composition on e-ink hardware."""
    if not hardware.is_available():
        return OperationResponse(
            success=False,
            error="Hardware not available",
        )

    # Render composition
    layers = composer.get_visible_layers()
    img = renderer.render_layers(layers, composer.width, composer.height)

    # Display on hardware
    success = hardware.display_image(
        img,
        partial=request.partial,
        rotate=request.rotate,
        flip_h=request.flip_h,
        flip_v=request.flip_v,
    )

    if success:
        return OperationResponse(success=True, message="Displayed on hardware")
    else:
        return OperationResponse(success=False, error="Display failed")


@app.post("/api/clear-display", response_model=OperationResponse)
async def clear_display(color: int = 255):
    """Clear the e-ink display."""
    if not hardware.is_available():
        return OperationResponse(success=False, error="Hardware not available")

    success = hardware.clear(color)

    if success:
        return OperationResponse(success=True, message="Display cleared")
    else:
        return OperationResponse(success=False, error="Clear failed")


@app.get("/api/hardware-status")
async def get_hardware_status():
    """Get hardware status information."""
    return hardware.get_status()


# --- Template Endpoints ---


@app.get("/api/templates")
async def list_templates():
    """List all available templates."""
    return {"templates": templates.list_templates()}


@app.post("/api/templates", response_model=OperationResponse)
async def save_template(request: TemplateExportRequest):
    """Save current composition as template."""
    composition = composer.to_dict()
    success = templates.save_template(
        request.name,
        composition,
        request.description,
    )

    if success:
        return OperationResponse(success=True, message="Template saved")
    else:
        return OperationResponse(success=False, error="Failed to save template")


@app.get("/api/templates/{name}")
async def load_template(name: str):
    """Load a template."""
    template = templates.load_template(name)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Load into composer
    composer.from_dict(template)

    return {"success": True, "template": template}


@app.delete("/api/templates/{name}", response_model=OperationResponse)
async def delete_template(name: str):
    """Delete a template."""
    success = templates.delete_template(name)

    if success:
        return OperationResponse(success=True, message="Template deleted")
    else:
        return OperationResponse(success=False, error="Template not found")


# --- Static Files ---

# Get the directory containing this file
current_dir = Path(__file__).parent

# Mount static files
static_dir = current_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Serve index.html at root
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main application."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    else:
        return HTMLResponse(content="<h1>E-ink Composer</h1><p>Static files not found.</p>")


# --- Debug Endpoints ---


@app.get("/api/debug/status")
async def get_debug_status():
    """Get debug statistics and status."""
    return debug_manager.get_stats()


@app.post("/api/debug/toggle")
async def toggle_debug(enabled: bool | None = None):
    """Toggle debug mode on/off."""
    new_state = debug_manager.toggle_debug(enabled)
    return {
        "debug_mode": new_state,
        "message": f"Debug mode {'enabled' if new_state else 'disabled'}",
    }


@app.get("/api/debug/layers")
async def debug_layers():
    """Get detailed layer state for debugging."""
    if not debug_manager.is_enabled():
        return {"error": "Debug mode not enabled"}

    state = {
        "composer": {
            "width": composer.width,
            "height": composer.height,
            "layer_count": len(composer.layers),
            "layer_order": composer.layer_order,
            "layers": {lid: str(layer.__dict__) for lid, layer in composer.layers.items()},
        },
        "hardware": hardware.get_status(),
    }
    debug_manager.dump_state(state, "Layer State Dump")
    return state


if __name__ == "__main__":
    import uvicorn

    info("Starting E-ink Composer Web Application")
    uvicorn.run(app, host="0.0.0.0", port=5000)
